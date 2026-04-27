"""
项目文件管理服务
提供文件浏览、读取、编辑等功能
"""
import os
from typing import List, Dict, Optional
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 二进制文件扩展名
BINARY_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dll', '.exe',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.db', '.sqlite', '.sqlite3',
    '.class', '.jar', '.war'
}

# 允许编辑的文件类型
EDITABLE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.json', '.yaml', '.yml', '.xml', '.html', '.css',
    '.md', '.txt', '.rst', '.log',
    '.cfg', '.ini', '.conf', '.env',
    '.sh', '.bash', '.bat', '.cmd',
    '.sql', '.graphql', '.toml',
    '.dockerfile', '.gitignore', '.gitattributes'
}


class FileService:
    """文件管理服务"""
    
    def __init__(self, base_path: str):
        """
        初始化文件服务
        
        Args:
            base_path: 项目根目录路径
        """
        self.base_path = os.path.abspath(base_path)
        
        # 确保目录存在
        if not os.path.exists(self.base_path):
            raise ValueError(f"项目目录不存在: {self.base_path}")
    
    def _safe_path(self, relative_path: str) -> str:
        """
        安全路径转换，防止路径穿越攻击
        
        Args:
            relative_path: 相对路径
            
        Returns:
            绝对路径
        """
        # 转换为绝对路径
        full_path = os.path.abspath(os.path.join(self.base_path, relative_path))
        
        # 检查是否在base_path内
        if not full_path.startswith(self.base_path):
            raise ValueError("非法路径访问")
        
        return full_path
    
    def get_file_tree(self, relative_path: str = "", max_depth: int = 3) -> Dict:
        """
        获取文件树结构
        
        Args:
            relative_path: 相对路径
            max_depth: 最大深度
            
        Returns:
            文件树结构
        """
        try:
            target_path = self._safe_path(relative_path)
            
            if not os.path.exists(target_path):
                return {"error": "路径不存在"}
            
            return self._build_tree(target_path, self.base_path, max_depth)
        except Exception as e:
            logger.error(f"Failed to get file tree: {e}")
            return {"error": str(e)}
    
    def _build_tree(self, path: str, base_path: str, max_depth: int, current_depth: int = 0) -> Dict:
        """
        递归构建文件树
        
        Args:
            path: 当前路径
            base_path: 基础路径
            max_depth: 最大深度
            current_depth: 当前深度
            
        Returns:
            文件树节点
        """
        name = os.path.basename(path)
        relative_path = os.path.relpath(path, base_path)
        
        # 跳过隐藏文件和常见忽略目录
        if name.startswith('.') and name not in ['.env', '.gitignore']:
            return None
        
        # 跳过常见忽略目录
        skip_dirs = {'node_modules', '__pycache__', '.git', '.venv', 'venv', 'env'}
        if os.path.isdir(path) and name in skip_dirs:
            return None
        
        # 跳过常见忽略文件
        skip_files = {
            'adaptive_fingerprints.db', 'fingerprints.db', 'requests.db',
            'scrapy.cfg',
            '.DS_Store', 'Thumbs.db',
            'run_exists_checker.py',
        }
        if name in skip_files:
            return None
        
        node = {
            "name": name,
            "path": relative_path,
            "type": "directory" if os.path.isdir(path) else "file"
        }
        
        if os.path.isdir(path):
            # 目录
            if current_depth < max_depth:
                children = []
                try:
                    items = sorted(os.listdir(path))
                    # 目录排在前面，文件排在后面
                    dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
                    files = [i for i in items if os.path.isfile(os.path.join(path, i))]
                    for item in dirs + files:
                        child_path = os.path.join(path, item)
                        child_node = self._build_tree(
                            child_path, base_path, max_depth, current_depth + 1
                        )
                        if child_node:
                            children.append(child_node)
                except PermissionError:
                    pass
                
                node["children"] = children
        else:
            # 文件
            try:
                stat = os.stat(path)
                node["size"] = stat.st_size
                node["extension"] = os.path.splitext(name)[1]
                node["modified_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except:
                pass
        
        return node
    
    def read_file(self, relative_path: str) -> Dict:
        """
        读取文件内容
        
        Args:
            relative_path: 相对路径
            
        Returns:
            文件内容信息
        """
        try:
            target_path = self._safe_path(relative_path)
            
            if not os.path.exists(target_path):
                return {"error": "文件不存在"}
            
            if os.path.isdir(target_path):
                return {"error": "不能读取目录"}
            
            # 检查文件大小（限制1MB）
            file_size = os.path.getsize(target_path)
            if file_size > 1024 * 1024:
                return {"error": "文件太大（超过1MB）"}
            
            # 检查是否为二进制文件
            extension = os.path.splitext(target_path)[1].lower()
            is_binary = extension in BINARY_EXTENSIONS
            
            if is_binary:
                return {
                    "path": relative_path,
                    "content": "",
                    "encoding": "binary",
                    "size": file_size,
                    "is_binary": True
                }
            
            # 读取文件内容
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            content = None
            used_encoding = 'utf-8'
            
            for encoding in encodings:
                try:
                    with open(target_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if content is None:
                return {
                    "path": relative_path,
                    "content": "",
                    "encoding": "unknown",
                    "size": file_size,
                    "is_binary": True
                }
            
            return {
                "path": relative_path,
                "content": content,
                "encoding": used_encoding,
                "size": file_size,
                "is_binary": False
            }
            
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return {"error": str(e)}
    
    def write_file(self, relative_path: str, content: str) -> Dict:
        """
        写入文件内容
        
        Args:
            relative_path: 相对路径
            content: 文件内容
            
        Returns:
            操作结果
        """
        try:
            target_path = self._safe_path(relative_path)
            
            # 检查扩展名是否允许编辑
            extension = os.path.splitext(target_path)[1].lower()
            if extension and extension not in EDITABLE_EXTENSIONS:
                return {"success": False, "message": f"不支持编辑 {extension} 文件"}
            
            # 确保父目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # 写入文件
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": "文件保存成功",
                "data": {"path": relative_path, "size": len(content)}
            }
            
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            return {"success": False, "message": f"保存失败: {str(e)}"}
    
    def create_file(self, relative_path: str, is_directory: bool = False) -> Dict:
        """
        创建文件或目录
        
        Args:
            relative_path: 相对路径
            is_directory: 是否创建目录
            
        Returns:
            操作结果
        """
        try:
            target_path = self._safe_path(relative_path)
            
            if os.path.exists(target_path):
                return {"success": False, "message": "文件/目录已存在"}
            
            if is_directory:
                os.makedirs(target_path, exist_ok=True)
                return {"success": True, "message": "目录创建成功"}
            else:
                # 确保父目录存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                Path(target_path).touch()
                return {"success": True, "message": "文件创建成功"}
                
        except Exception as e:
            logger.error(f"Failed to create: {e}")
            return {"success": False, "message": f"创建失败: {str(e)}"}
    
    def delete_file(self, relative_path: str) -> Dict:
        """
        删除文件或目录
        
        Args:
            relative_path: 相对路径
            
        Returns:
            操作结果
        """
        try:
            target_path = self._safe_path(relative_path)
            
            if not os.path.exists(target_path):
                return {"success": False, "message": "文件/目录不存在"}
            
            if os.path.isdir(target_path):
                import shutil
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            
            return {"success": True, "message": "删除成功"}
            
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            return {"success": False, "message": f"删除失败: {str(e)}"}
    
    def rename_file(self, old_relative_path: str, new_name: str) -> Dict:
        """
        重命名文件或目录
        
        Args:
            old_relative_path: 原相对路径
            new_name: 新名称
            
        Returns:
            操作结果
        """
        try:
            old_path = self._safe_path(old_relative_path)
            
            if not os.path.exists(old_path):
                return {"success": False, "message": "文件/目录不存在"}
            
            # 新路径
            parent_dir = os.path.dirname(old_path)
            new_path = os.path.join(parent_dir, new_name)
            
            if os.path.exists(new_path):
                return {"success": False, "message": "目标名称已存在"}
            
            os.rename(old_path, new_path)
            
            return {"success": True, "message": "重命名成功"}
            
        except Exception as e:
            logger.error(f"Failed to rename: {e}")
            return {"success": False, "message": f"重命名失败: {str(e)}"}
