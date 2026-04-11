"""Git 操作服务
提供完整的 Git 功能：克隆、拉取、推送、分支管理、提交历史等
"""
import os
import git
import tempfile
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GitService:
    """Git 操作服务"""
    
    def __init__(self, repo_dir: str):
        """
        初始化 Git 服务
        
        Args:
            repo_dir: 仓库本地路径
        """
        self.repo_dir = repo_dir
        self.repo = None
        
        # 确保目录存在
        os.makedirs(repo_dir, exist_ok=True)
    
    def initialize_repo(self) -> bool:
        """初始化空仓库"""
        try:
            if not os.path.exists(os.path.join(self.repo_dir, '.git')):
                self.repo = git.Repo.init(self.repo_dir)
                logger.info(f"Initialized git repo at {self.repo_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize repo: {e}")
            raise
    
    def clone_repository(self, url: str, branch: Optional[str] = None, 
                        username: Optional[str] = None, 
                        password: Optional[str] = None,
                        auth_type: str = "password",
                        ssh_key: Optional[str] = None,
                        passphrase: Optional[str] = None) -> Dict:
        """
        克隆远程仓库
        
        Args:
            url: Git 仓库 URL
            branch: 分支名（可选）
            username: 用户名（可选）
            password: 密码（可选）
            auth_type: 认证类型 (password 或 ssh)
            ssh_key: SSH私钥内容（可选）
            passphrase: SSH私钥密码（可选）
        
        Returns:
            克隆信息
        """
        ssh_key_path = None
        original_env = None
        
        try:
            # 处理SSH认证
            if auth_type == "ssh" and ssh_key:
                # 创建临时SSH密钥文件
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    delete=False,
                    prefix='ssh_key_',
                    suffix='.pem'
                ) as f:
                    f.write(ssh_key)
                    ssh_key_path = f.name
                
                # 设置权限（必须是600）
                os.chmod(ssh_key_path, 0o600)
                
                # 构建SSH命令
                ssh_command = f'ssh -i {ssh_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                
                # 如果有passphrase，使用sshpass
                if passphrase:
                    ssh_command = f'sshpass -p "{passphrase}" ' + ssh_command
                
                # 保存原始环境变量
                original_env = os.environ.get('GIT_SSH_COMMAND')
                
                # 设置环境变量
                os.environ['GIT_SSH_COMMAND'] = ssh_command
            
            # 处理密码认证
            clone_url = url
            if auth_type == "password" and username and password:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(url)
                clone_url = urlunparse((
                    parsed.scheme,
                    f"{username}:{password}@{parsed.netloc}",
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
            
            clone_options = {
                'url': clone_url,
                'path': self.repo_dir,
                'depth': 1,  # 浅克隆，加快速度
            }
            
            if branch:
                clone_options['branch'] = branch
            
            self.repo = git.Repo.clone_from(**clone_options)
            
            logger.info(f"Cloned repository from {url} with {auth_type} auth")
            return {
                'success': True,
                'message': f'成功克隆仓库: {url}',
                'branch': branch or 'main',
                'path': self.repo_dir
            }
        except git.GitCommandError as e:
            logger.error(f"Failed to clone repository: {e}")
            raise Exception(f"克隆失败: {str(e)}")
        finally:
            # 清理SSH密钥文件
            if ssh_key_path and os.path.exists(ssh_key_path):
                try:
                    os.remove(ssh_key_path)
                    logger.info(f"Removed temporary SSH key file: {ssh_key_path}")
                except Exception as e:
                    logger.error(f"Failed to remove SSH key file: {e}")
            
            # 恢复环境变量
            if original_env is not None:
                os.environ['GIT_SSH_COMMAND'] = original_env
            elif 'GIT_SSH_COMMAND' in os.environ:
                del os.environ['GIT_SSH_COMMAND']
    
    def pull(self, remote: str = 'origin', branch: Optional[str] = None) -> Dict:
        """
        拉取远程更新
        
        Args:
            remote: 远程仓库名
            branch: 分支名
        
        Returns:
            拉取结果
        """
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            current_branch = self.repo.active_branch.name
            pull_branch = branch or current_branch
            
            result = self.repo.remotes[remote].pull(pull_branch)
            
            return {
                'success': True,
                'message': f'成功拉取 {remote}/{pull_branch}',
                'commits': len(result),
                'branch': pull_branch
            }
        except Exception as e:
            logger.error(f"Failed to pull: {e}")
            raise Exception(f"拉取失败: {str(e)}")
    
    def push(self, remote: str = 'origin', branch: Optional[str] = None,
            username: Optional[str] = None, password: Optional[str] = None,
            auth_type: str = "password", ssh_key: Optional[str] = None,
            passphrase: Optional[str] = None) -> Dict:
        """
        推送到远程仓库
        
        Args:
            remote: 远程仓库名
            branch: 分支名
            username: 用户名
            password: 密码
            auth_type: 认证类型
            ssh_key: SSH私钥内容
            passphrase: SSH私钥密码
        
        Returns:
            推送结果
        """
        ssh_key_path = None
        original_env = None
        
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            current_branch = self.repo.active_branch.name
            push_branch = branch or current_branch
            
            # 处理SSH认证
            if auth_type == "ssh" and ssh_key:
                # 创建临时SSH密钥文件
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    delete=False,
                    prefix='ssh_key_',
                    suffix='.pem'
                ) as f:
                    f.write(ssh_key)
                    ssh_key_path = f.name
                
                # 设置权限
                os.chmod(ssh_key_path, 0o600)
                
                # 构建SSH命令
                ssh_command = f'ssh -i {ssh_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                
                if passphrase:
                    ssh_command = f'sshpass -p "{passphrase}" ' + ssh_command
                
                # 保存原始环境变量
                original_env = os.environ.get('GIT_SSH_COMMAND')
                os.environ['GIT_SSH_COMMAND'] = ssh_command
            elif auth_type == "password" and username and password:
                # 设置密码认证
                self._set_credentials(remote, username, password)
            
            result = self.repo.remotes[remote].push(push_branch)
            
            return {
                'success': True,
                'message': f'成功推送到 {remote}/{push_branch}',
                'branch': push_branch
            }
        except Exception as e:
            logger.error(f"Failed to push: {e}")
            raise Exception(f"推送失败: {str(e)}")
        finally:
            # 清理SSH密钥文件
            if ssh_key_path and os.path.exists(ssh_key_path):
                try:
                    os.remove(ssh_key_path)
                except Exception as e:
                    logger.error(f"Failed to remove SSH key file: {e}")
            
            # 恢复环境变量
            if original_env is not None:
                os.environ['GIT_SSH_COMMAND'] = original_env
            elif 'GIT_SSH_COMMAND' in os.environ:
                del os.environ['GIT_SSH_COMMAND']
    
    def get_branches(self, remote: bool = False) -> List[str]:
        """获取分支列表"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            if remote:
                return [ref.name for ref in self.repo.remotes.origin.refs]
            else:
                return [ref.name for ref in self.repo.refs]
        except Exception as e:
            logger.error(f"Failed to get branches: {e}")
            return []
    
    def create_branch(self, branch_name: str, start_point: str = 'HEAD') -> Dict:
        """创建新分支"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            self.repo.create_head(branch_name, start_point)
            
            return {
                'success': True,
                'message': f'创建分支: {branch_name}',
                'branch': branch_name
            }
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            raise Exception(f"创建分支失败: {str(e)}")
    
    def checkout_branch(self, branch_name: str) -> Dict:
        """切换分支"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            self.repo.heads[branch_name].checkout()
            
            return {
                'success': True,
                'message': f'切换到分支: {branch_name}',
                'branch': branch_name
            }
        except Exception as e:
            logger.error(f"Failed to checkout branch: {e}")
            raise Exception(f"切换分支失败: {str(e)}")
    
    def get_commit_history(self, max_count: int = 50) -> List[Dict]:
        """获取提交历史"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            commits = []
            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append({
                    'hash': commit.hexsha,
                    'short_hash': commit.hexsha[:8],
                    'author': str(commit.author),
                    'email': commit.author.email,
                    'message': commit.message.strip(),
                    'date': datetime.fromtimestamp(commit.committed_date).isoformat(),
                    'parents': [p.hexsha for p in commit.parents]
                })
            
            return commits
        except Exception as e:
            logger.error(f"Failed to get commit history: {e}")
            return []
    
    def get_tags(self) -> List[str]:
        """获取标签列表"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            return [tag.name for tag in self.repo.tags]
        except Exception as e:
            logger.error(f"Failed to get tags: {e}")
            return []
    
    def create_tag(self, tag_name: str, message: str = '') -> Dict:
        """创建标签"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            self.repo.create_tag(tag_name, message=message)
            
            return {
                'success': True,
                'message': f'创建标签: {tag_name}',
                'tag': tag_name
            }
        except Exception as e:
            logger.error(f"Failed to create tag: {e}")
            raise Exception(f"创建标签失败: {str(e)}")
    
    def get_status(self) -> Dict:
        """获取仓库状态"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            return {
                'branch': self.repo.active_branch.name,
                'is_dirty': self.repo.is_dirty(),
                'untracked_files': self.repo.untracked_files,
                'changed_files': [item.a_path for item in self.repo.index.diff(None)],
                'staged_files': [item.a_path for item in self.repo.index.diff('HEAD')]
            }
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {}
    
    def add_files(self, files: List[str] = None) -> Dict:
        """添加文件到暂存区"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            if files:
                self.repo.index.add(files)
            else:
                self.repo.index.add(['*'])
            
            return {
                'success': True,
                'message': '文件已添加到暂存区'
            }
        except Exception as e:
            logger.error(f"Failed to add files: {e}")
            raise Exception(f"添加文件失败: {str(e)}")
    
    def commit(self, message: str) -> Dict:
        """提交更改"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            commit = self.repo.index.commit(message)
            
            return {
                'success': True,
                'message': '提交成功',
                'commit_hash': commit.hexsha[:8]
            }
        except Exception as e:
            logger.error(f"Failed to commit: {e}")
            raise Exception(f"提交失败: {str(e)}")
    
    def _set_credentials(self, remote: str, username: str, password: str):
        """设置 Git 认证"""
        try:
            if not self.repo:
                self.repo = git.Repo(self.repo_dir)
            
            # 使用 credential helper 存储凭据
            self.repo.git.config('credential.helper', 'store')
            
            # 写入凭据文件
            cred_file = os.path.join(self.repo_dir, '.git-credentials')
            url = self.repo.remotes[remote].url
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            cred_url = urlunparse((
                parsed.scheme,
                f"{username}:{password}@{parsed.netloc}",
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            with open(cred_file, 'w') as f:
                f.write(cred_url + '\n')
        except Exception as e:
            logger.error(f"Failed to set credentials: {e}")
