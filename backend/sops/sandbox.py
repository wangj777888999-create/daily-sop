# backend/sops/sandbox.py
"""
沙箱执行器 - 在隔离环境中安全执行 Python 代码
"""
import subprocess
import tempfile
import os
import signal
import re
from typing import Dict, Any, Optional
from pathlib import Path


class SandboxExecutor:
    """沙箱执行器 - 在隔离环境中执行 Python 代码"""

    DEFAULT_TIMEOUT = 60  # 秒

    # 禁止的导入模块
    BLOCKED_IMPORTS = [
        'os', 'sys', 'subprocess', 'socket',
        'urllib', 'http', 'requests', 'ftplib',
        'smtplib', 'pickle', 'eval', 'exec', 'open',
        'pathlib', 'glob', 'shutil', 'tempfile',
        'commands', 'ast', 'builtins',
    ]

    # 允许的导入模块（安全模块）
    ALLOWED_IMPORTS = [
        'pandas', 'numpy', 'math', 'json', 're',
        'datetime', 'collections', 'itertools', 'functools',
        'typing', 'decimal', 'random', 'statistics',
    ]

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        初始化沙箱执行器

        Args:
            timeout: 超时时间（秒），默认 60 秒
        """
        self.timeout = timeout

    def execute(self, code: str) -> Dict[str, Any]:
        """
        执行代码并返回结果

        Args:
            code: Python 代码字符串

        Returns:
            包含执行结果的字典:
            - success: bool, 是否执行成功
            - output: str, stdout 输出
            - error: str, 错误信息（如果有）
            - return_code: int, 进程返回码
        """
        result = {
            'success': False,
            'output': '',
            'error': '',
            'return_code': -1
        }

        # 验证代码安全性
        validation_error = self._validate_imports(code)
        if validation_error:
            result['error'] = validation_error
            return result

        # 写入临时文件
        temp_file = self._write_temp_file(code)

        try:
            # 构建执行命令 - 使用 python3 运行
            cmd = ['python3', temp_file]

            # 使用 subprocess 执行，设置超时
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._get_safe_env()
            )

            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                result['output'] = stdout
                result['error'] = stderr
                result['return_code'] = process.returncode
                result['success'] = process.returncode == 0
            except subprocess.TimeoutExpired:
                # 超时，终止进程
                process.kill()
                process.communicate()
                result['error'] = f'代码执行超时（超过 {self.timeout} 秒）'
                result['return_code'] = -1

        except Exception as e:
            result['error'] = f'执行异常: {str(e)}'
            result['return_code'] = -1

        finally:
            # 清理临时文件
            self._cleanup_temp_file(temp_file)

        return result

    def _validate_imports(self, code: str) -> Optional[str]:
        """
        检查是否有禁止的导入

        Args:
            code: Python 代码字符串

        Returns:
            如果验证通过返回 None，否则返回错误信息
        """
        # 提取所有 import 语句
        import_pattern = r'^(?:from\s+(\w+)|import\s+([\w,\s]+))'
        from_import_pattern = r'^from\s+(\w+)\s+import'

        lines = code.split('\n')
        for line in lines:
            line = line.strip()

            # 检查 from ... import 语句
            from_match = re.match(r'^from\s+(\w+)', line)
            if from_match:
                module_name = from_match.group(1)
                if module_name in self.BLOCKED_IMPORTS:
                    return f'禁止导入危险模块: {module_name}'
                continue

            # 检查 import ... 语句
            import_match = re.match(r'^import\s+([\w,\s]+)', line)
            if import_match:
                modules = import_match.group(1)
                for module in modules.split(','):
                    module = module.strip()
                    if module in self.BLOCKED_IMPORTS:
                        return f'禁止导入危险模块: {module}'

        return None

    def _write_temp_file(self, code: str) -> str:
        """
        写入临时文件

        Args:
            code: Python 代码

        Returns:
            临时文件路径
        """
        # 创建临时目录（如果不存在）
        temp_dir = Path(tempfile.gettempdir()) / 'sandbox_execution'
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        fd, temp_file = tempfile.mkstemp(suffix='.py', dir=str(temp_dir))
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(code)
        except Exception:
            # 如果写入失败，关闭文件描述符
            os.close(fd)
            raise

        return temp_file

    def _cleanup_temp_file(self, temp_file: str) -> None:
        """
        清理临时文件

        Args:
            temp_file: 临时文件路径
        """
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except Exception:
            pass

    def _get_safe_env(self) -> Dict[str, str]:
        """
        获取安全的环境变量

        Returns:
            环境变量字典
        """
        # 只保留必要的环境变量
        safe_env = {
            'PATH': '/usr/bin:/bin',  # 限制 PATH
            'HOME': os.environ.get('HOME', '/tmp'),
            'LANG': 'en_US.UTF-8',
            'LANGUAGE': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
        }
        return safe_env


def execute_code(code: str, timeout: int = 60) -> Dict[str, Any]:
    """
    执行 Python 代码的便捷函数

    Args:
        code: Python 代码字符串
        timeout: 超时时间（秒），默认 60 秒

    Returns:
        包含执行结果的字典:
        - success: bool, 是否执行成功
        - output: str, stdout 输出
        - error: str, 错误信息（如果有）
        - return_code: int, 进程返回码
    """
    executor = SandboxExecutor(timeout=timeout)
    return executor.execute(code)


# 简单的测试代码
if __name__ == '__main__':
    # 测试1: 正常执行
    print("测试1: 正常执行")
    result = execute_code('''
import pandas as pd
import numpy as np

df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
print(df.head())
print("执行成功!")
''')
    print(f"success: {result['success']}")
    print(f"output: {result['output']}")
    print(f"error: {result['error']}")
    print()

    # 测试2: 危险导入
    print("测试2: 危险导入检测")
    result = execute_code('''
import os
print(os.listdir())
''')
    print(f"success: {result['success']}")
    print(f"error: {result['error']}")
    print()

    # 测试3: 超时测试
    print("测试3: 超时控制")
    result = execute_code('''
import time
time.sleep(10)
print("done")
''', timeout=2)
    print(f"success: {result['success']}")
    print(f"error: {result['error']}")
