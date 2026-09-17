@echo off
REM 设置 HuggingFace 和 PyTorch 缓存到 D 盘
setx HF_HOME "D:\AAA\cache\huggingface"
setx TORCH_HOME "D:\AAA\cache\torch"
echo Environment variables set. Restart terminal to take effect.
echo HF_HOME=D:\AAA\cache\huggingface
echo TORCH_HOME=D:\AAA\cache\torch
