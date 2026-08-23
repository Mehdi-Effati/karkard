# اگر به‌جای mysqlclient از pymysql استفاده می‌کنید (مثلا روی ویندوز که نصب mysqlclient سخت‌تره)،
# این بخش خودش pymysql را جای MySQLdb می‌نشاند. اگر mysqlclient نصب باشد یا اصلا MySQL
# استفاده نکنید (SQLite)، این تلاش بی‌اثر است و خطایی هم نمی‌دهد.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
