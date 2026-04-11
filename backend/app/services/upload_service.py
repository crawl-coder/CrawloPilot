"""
文件上传服务
支持本地代码包上传、解压和管理
"""
import os
import shutil
import zipfile
import tarfile
from typing import Dict, Optional
from datetime import datetime
import logging
from fastapi import UploadFile
import uuid

logger = logging.getLogger(__name__)


class UploadService:
    """文件上传服务"""
    
    def __init__(self, upload_base_dir: str = "uploads"):
        """
        初始化上传服务
        
        Args:
            upload_base_dir: 上传文件基础目录
        """
        self.upload_base_dir = upload_base_dir
        os.makedirs(upload_base_dir, exist_ok=True)
    
    async def upload_code_package(self, file: UploadFile, project_id: int) -> Dict:
        """
        上传代码包（支持 ZIP/TAR）
        
        Args:
            file: 上传的文件
            project_id: 项目ID
        
        Returns:
            上传结果
        """
        # 验证文件类型
        allowed_extensions = {'.zip', '.tar', '.gz', '.bz2'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise ValueError(f"不支持的文件类型: {file_ext}，支持: {allowed_extensions}")
        
        # 创建项目上传目录
        project_upload_dir = os.path.join(self.upload_base_dir, f"project_{project_id}")
        os.makedirs(project_upload_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{unique_id}{file_ext}"
        file_path = os.path.join(project_upload_dir, filename)
        
        # 保存文件
        try:
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            
            file_size = len(content)
            logger.info(f"Uploaded file: {filename} ({file_size} bytes)")
            
            # 解压文件
            extract_dir = os.path.join(project_upload_dir, f"{timestamp}_{unique_id}_extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            extracted_files = await self._extract_archive(file_path, extract_dir)
            
            return {
                'success': True,
                'message': '上传并解压成功',
                'filename': filename,
                'file_size': file_size,
                'file_path': file_path,
                'extract_dir': extract_dir,
                'extracted_files': len(extracted_files),
                'uploaded_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise Exception(f"上传失败: {str(e)}")
    
    async def _extract_archive(self, file_path: str, extract_dir: str) -> list:
        """
        解压归档文件
        
        Args:
            file_path: 归档文件路径
            extract_dir: 解压目录
        
        Returns:
            解压的文件列表
        """
        extracted_files = []
        
        try:
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    extracted_files = zip_ref.namelist()
            elif file_path.endswith('.tar') or file_path.endswith('.gz') or file_path.endswith('.bz2'):
                with tarfile.open(file_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_dir)
                    extracted_files = tar_ref.getnames()
            else:
                raise ValueError(f"不支持的归档格式: {file_path}")
            
            logger.info(f"Extracted {len(extracted_files)} files to {extract_dir}")
            return extracted_files
            
        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            raise Exception(f"解压失败: {str(e)}")
    
    def list_uploaded_files(self, project_id: int) -> list:
        """列出项目的所有上传文件"""
        project_upload_dir = os.path.join(self.upload_base_dir, f"project_{project_id}")
        
        if not os.path.exists(project_upload_dir):
            return []
        
        files = []
        for filename in os.listdir(project_upload_dir):
            file_path = os.path.join(project_upload_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        
        # 按创建时间排序
        files.sort(key=lambda x: x['created_at'], reverse=True)
        return files
    
    def get_project_code_dir(self, project_id: int) -> Optional[str]:
        """获取项目的代码目录（最新的解压目录）"""
        project_upload_dir = os.path.join(self.upload_base_dir, f"project_{project_id}")
        
        if not os.path.exists(project_upload_dir):
            return None
        
        # 查找最新的解压目录
        extract_dirs = []
        for dirname in os.listdir(project_upload_dir):
            dir_path = os.path.join(project_upload_dir, dirname)
            if os.path.isdir(dir_path) and dirname.endswith('_extracted'):
                extract_dirs.append(dir_path)
        
        if not extract_dirs:
            return None
        
        # 返回最新的目录
        extract_dirs.sort(key=lambda x: os.path.getctime(x), reverse=True)
        return extract_dirs[0]
    
    def get_spider_code_dir(self, project_id: int, spider_id: int) -> Optional[str]:
        """获取爬虫的代码目录"""
        # 爬虫代码存储在 project_{project_id}/spider_{spider_id}/
        spider_dir = os.path.join(self.upload_base_dir, f"project_{project_id}", f"spider_{spider_id}")
        
        if not os.path.exists(spider_dir):
            # 如果不存在，尝试使用项目的代码目录
            return self.get_project_code_dir(project_id)
        
        return spider_dir
    
    def delete_uploaded_file(self, project_id: int, filename: str) -> bool:
        """删除上传的文件"""
        file_path = os.path.join(self.upload_base_dir, f"project_{project_id}", filename)
        
        if not os.path.exists(file_path):
            return False
        
        try:
            os.remove(file_path)
            
            # 同时删除对应的解压目录
            extract_dir = file_path.replace('.zip', '_extracted').replace('.tar', '_extracted')
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            
            logger.info(f"Deleted uploaded file: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
