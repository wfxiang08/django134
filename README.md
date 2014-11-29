# Django 1.3.4的修改
- collectstatic采用md5 + 时间戳 双重判断。因为git的checkout,branch的调整可能会将大量的文件的last modified给修改。导致collectstatic非常耗时
- 将之前手动修改的admin中关于query权限添加上

## 项目信息
- [Pypi地址](http://pypi.chunyu.mobi/packages/Django/)
- 安装
```bash
smart_update.py -f Django==1.3.4-dev
```