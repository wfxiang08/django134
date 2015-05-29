# Django 1.3.4的修改
- collectstatic采用md5 + 时间戳 双重判断。因为git的checkout,branch的调整可能会将大量的文件的last modified给修改。导致collectstatic非常耗时
- 将之前手动修改的admin中关于query权限添加上

## 项目信息
- [Pypi地址](http://pypi.chunyu.mobi/packages/Django/)
- 安装
```bash
smart_update.py -f Django==1.3.4-dev
```

## 增加了Model的删除保护

```python
# 在settings中增加: DELETE_PROTECTED_APPS
DELETED_OTHER_APPS = ('django.contrib.auth',)
DELETE_PROTECTED_APPS = set() # 定义了被Django保护的Models
for app in (CHUNYU_APPS + DELETED_OTHER_APPS):
    app_label = app.split(".")[-1]
    DELETE_PROTECTED_APPS.add(app_label)

# 然后这些app下的model就不能直接调用如下方法
User.objects.get(id=1).delete()

User.objects.filter(id__in=[1,2]).delete()

```
