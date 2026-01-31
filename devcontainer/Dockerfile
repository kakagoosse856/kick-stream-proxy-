FROM mcr.microsoft.com/vscode/devcontainers/python:3.11

# تحديث pip
RUN python -m pip install --upgrade pip

# تثبيت المكتبات الأساسية
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
