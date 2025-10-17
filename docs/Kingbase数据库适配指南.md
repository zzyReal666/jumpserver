# JumpServer适配Kingbase数据库完整指南

> 基于 `feat: 添加HighGo数据库支持` (commit: cfdbcc4dd) 的实现模式

---

## 一、适配概述

**Kingbase（人大金仓）** 是一款国产关系型数据库，兼容PostgreSQL协议。本文档将指导你完成在JumpServer中添加Kingbase数据库支持的完整流程。

### 需要修改的文件（共9个）

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `apps/assets/const/database.py` | 修改 | 添加数据库类型定义 |
| `apps/assets/const/protocol.py` | 修改 | 添加协议配置 |
| `apps/terminal/connect_methods.py` | 修改 | 添加连接方法支持 |
| `apps/terminal/models/component/endpoint.py` | 修改 | 添加端口字段 |
| `apps/terminal/migrations/0011_endpoint_kingbase_port.py` | 新建 | 数据库迁移文件 |
| `apps/assets/automations/ping/database/kingbase/main.yml` | 新建 | Ping自动化配置 |
| `apps/assets/automations/ping/database/kingbase/manifest.yml` | 新建 | Ping元数据配置 |
| `apps/assets/automations/gather_facts/database/kingbase/main.yml` | 新建 | 信息收集配置 |
| `apps/assets/automations/gather_facts/database/kingbase/manifest.yml` | 新建 | 信息收集元数据 |

---

## 二、详细实施步骤

### 步骤1：添加数据库类型定义

**文件：** `apps/assets/const/database.py`

#### 位置1 - 添加类型常量（第17行后）

```python
class DatabaseTypes(BaseType):
    MYSQL = 'mysql', 'MySQL'
    MARIADB = 'mariadb', 'MariaDB'
    POSTGRESQL = 'postgresql', 'PostgreSQL'
    ORACLE = 'oracle', 'Oracle'
    SQLSERVER = 'sqlserver', 'SQLServer'
    DB2 = 'db2', 'DB2'
    DAMENG = 'dameng', 'Dameng'
    CLICKHOUSE = 'clickhouse', 'ClickHouse'
    MONGODB = 'mongodb', 'MongoDB'
    REDIS = 'redis', 'Redis'
    HIGHGO = 'highgo', 'HighGo'
    KINGBASE = 'kingbase', 'Kingbase'  # 新增这一行
```

#### 位置2 - 添加内部平台配置（第118行后）

```python
            ],
            cls.HIGHGO: [{'name': 'HighGo'}],
            cls.KINGBASE: [{'name': 'Kingbase'}]  # 新增这一行
        }
```

#### 位置3 - 添加到社区版支持列表（第125行）

```python
    @classmethod
    def get_community_types(cls):
        return [
            cls.MYSQL, cls.MARIADB, cls.POSTGRESQL,
            cls.MONGODB, cls.REDIS, cls.SQLSERVER, cls.ORACLE, 
            cls.DAMENG, cls.HIGHGO, cls.KINGBASE,  # 添加KINGBASE
        ]
```

---

### 步骤2：添加协议配置

**文件：** `apps/assets/const/protocol.py`

#### 位置1 - 添加协议常量（第29行后）

```python
    mongodb = 'mongodb', 'MongoDB'
    highgo = 'highgo', 'HighGo'
    kingbase = 'kingbase', 'Kingbase'  # 新增这一行

    k8s = 'k8s', 'K8s'
```

#### 位置2 - 添加协议详细配置（第268行后）

```python
            },
            cls.kingbase: {
                'port': 54321,  # Kingbase默认端口
                'required': True,
                'secret_types': ['password'],
                'xpack': True,
                'setting': {
                    'use_ssl': {
                        'type': 'bool',
                        'default': False,
                        'label': _('Use SSL'),
                        'help_text': _('Whether to use SSL connection')
                    },
                    'pg_ssl_mode': {
                        'type': 'select',
                        'default': 'prefer',
                        'label': _('SSL mode'),
                        'choices': [
                            ('prefer', 'Prefer'),
                            ('require', 'Require'),
                            ('verify-ca', 'Verify CA'),
                            ('verify-full', 'Verify Full'),
                        ],
                        'help_text': _('SSL connection mode')
                    },
                }
            },
        }
```

---

### 步骤3：添加连接方法支持

**文件：** `apps/terminal/connect_methods.py`

#### 位置1 - 添加到NativeClient支持（第57行）

```python
            Protocol.oracle: [cls.db_client, cls.db_guide],
            Protocol.postgresql: [cls.db_client, cls.db_guide],
            Protocol.sqlserver: [cls.db_client, cls.db_guide],
            Protocol.highgo: [cls.db_client],
            Protocol.kingbase: [cls.db_client],  # 新增这一行
            Protocol.vnc: [cls.vnc_guide, ]
```

#### 位置2 - 添加到db_client支持（第177行）

```python
                    Protocol.mysql, Protocol.postgresql,
                    Protocol.oracle, Protocol.sqlserver,
                    Protocol.mariadb, Protocol.db2,
                    Protocol.dameng, Protocol.highgo,
                    Protocol.kingbase  # 新增
                ],
```

#### 位置3 - 添加到db_guide支持（第194行）

```python
                    Protocol.mysql, Protocol.postgresql,
                    Protocol.oracle, Protocol.mariadb,
                    Protocol.redis, Protocol.sqlserver,
                    Protocol.mongodb, Protocol.highgo,
                    Protocol.kingbase  # 新增
                ],
```

---

### 步骤4：添加Endpoint端口字段

**文件：** `apps/terminal/models/component/endpoint.py`

#### 位置1 - 添加端口字段（第27行后）

```python
    mongodb_port = PortField(default=27018, verbose_name=_('MongoDB port'))
    highgo_port = PortField(default=58660, verbose_name=_('HighGo port'))
    kingbase_port = PortField(default=54322, verbose_name=_('Kingbase port'))  # 新增
    vnc_port = PortField(default=15900, verbose_name=_('VNC port'))
```

#### 位置2 - 添加默认值（第72行后）

```python
            'http_port': 0,
            'highgo_port': 0,
            'kingbase_port': 0,  # 新增
        }
```

---

### 步骤5：创建数据库迁移文件

**文件：** `apps/terminal/migrations/0011_endpoint_kingbase_port.py`（新建）

```python
# Generated by Django 4.1.13 on 2025-10-17 10:00

import common.db.fields
import django.core.validators
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0010_endpoint_highgo_port'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpoint',
            name='kingbase_port',
            field=common.db.fields.PortField(
                default=54322, 
                validators=[
                    django.core.validators.MinValueValidator(0), 
                    django.core.validators.MaxValueValidator(65535)
                ], 
                verbose_name='Kingbase port'
            ),
        ),
    ]
```

---

### 步骤6：创建Ping自动化配置

#### 创建目录

```bash
mkdir -p apps/assets/automations/ping/database/kingbase
```

#### 文件1：`apps/assets/automations/ping/database/kingbase/main.yml`

```yaml
- hosts: kingbase
  gather_facts: no
  vars:
    ansible_python_interpreter: "{{ local_python_interpreter }}"
    check_ssl: "{{ jms_asset.spec_info.use_ssl }}"
    ca_cert: "{{ jms_asset.secret_info.ca_cert | default('') }}"
    ssl_cert: "{{ jms_asset.secret_info.client_cert | default('') }}"
    ssl_key: "{{ jms_asset.secret_info.client_key | default('') }}"
    ansible_timeout: 30
  tasks:
    - name: Test Kingbase connection
      community.postgresql.postgresql_ping:
        login_user: "{{ jms_account.username }}"
        login_password: "{{ jms_account.secret }}"
        login_host: "{{ jms_asset.address }}"
        login_port: "{{ jms_asset.port }}"
        login_db: "{{ jms_asset.spec_info.db_name }}"
        ca_cert: "{{ ca_cert if check_ssl and ca_cert | length > 0 else omit }}"
        ssl_cert: "{{ ssl_cert if check_ssl and ssl_cert | length > 0 else omit }}"
        ssl_key: "{{ ssl_key if check_ssl and ssl_key | length > 0 else omit }}"
        ssl_mode: "{{ jms_asset.spec_info.pg_ssl_mode | default('prefer') }}"
      register: result
      failed_when: not result.is_available
```

#### 文件2：`apps/assets/automations/ping/database/kingbase/manifest.yml`

```yaml
id: kingbase_ping
name: "{{ 'Ping Kingbase' | trans }}"
category: database
type:
  - kingbase
method: ping
i18n:
  Ping Kingbase:
    zh: 使用 Ansible 模块 postgresql 来测试 Kingbase 可连接性
    en: Use ansible postgresql module to test Kingbase
    ja: Ansible postgresqlモジュールを使用してテストする Kingbase
```

---

### 步骤7：创建Gather Facts自动化配置

#### 创建目录

```bash
mkdir -p apps/assets/automations/gather_facts/database/kingbase
```

#### 文件1：`apps/assets/automations/gather_facts/database/kingbase/main.yml`

```yaml
- hosts: kingbase
  gather_facts: no
  vars:
    ansible_python_interpreter: "{{ local_python_interpreter }}"
    check_ssl: "{{ jms_asset.spec_info.use_ssl }}"
    ca_cert: "{{ jms_asset.secret_info.ca_cert | default('') }}"
    ssl_cert: "{{ jms_asset.secret_info.client_cert | default('') }}"
    ssl_key: "{{ jms_asset.secret_info.client_key | default('') }}"

  tasks:
    - name: Get Kingbase info
      community.postgresql.postgresql_info:
        login_user: "{{ jms_account.username }}"
        login_password: "{{ jms_account.secret }}"
        login_host: "{{ jms_asset.address }}"
        login_port: "{{ jms_asset.port }}"
        login_db: "{{ jms_asset.spec_info.db_name }}"
        ca_cert: "{{ ca_cert if check_ssl and ca_cert | length > 0 else omit }}"
        ssl_cert: "{{ ssl_cert if check_ssl and ssl_cert | length > 0 else omit }}"
        ssl_key: "{{ ssl_key if check_ssl and ssl_key | length > 0 else omit }}"
        ssl_mode: "{{ jms_asset.spec_info.pg_ssl_mode | default('prefer') }}"
      register: db_info

    - name: Define info by set_fact
      set_fact:
        info:
          version: "{{ db_info.server_version.raw }}"

    - debug:
        var: info
```

#### 文件2：`apps/assets/automations/gather_facts/database/kingbase/manifest.yml`

```yaml
id: gather_facts_kingbase
name: "{{ 'Gather facts from Kingbase' | trans }}"
category: database
type:
  - kingbase
method: gather_facts
i18n:
  Gather facts from Kingbase:
    zh: 使用 Ansible 模块 postgresql 从 Kingbase server 获取信息
    en: Gather facts from Kingbase server using postgresql module
    ja: postgresqlモジュールを使用して Kingbase serverから情報を収集する
```

---

## 三、实施检查清单

- [ ] 1. 修改 `apps/assets/const/database.py`（3处）
- [ ] 2. 修改 `apps/assets/const/protocol.py`（2处）
- [ ] 3. 修改 `apps/terminal/connect_methods.py`（3处）
- [ ] 4. 修改 `apps/terminal/models/component/endpoint.py`（2处）
- [ ] 5. 创建迁移文件 `apps/terminal/migrations/0011_endpoint_kingbase_port.py`
- [ ] 6. 创建 Ping 配置文件（2个文件）
- [ ] 7. 创建 Gather Facts 配置文件（2个文件）
- [ ] 8. 运行数据库迁移
- [ ] 9. 重启JumpServer服务
- [ ] 10. 测试Kingbase资产添加和连接

---

## 四、关键配置参数说明

| 参数 | 值 | 说明 |
|-----|-----|------|
| **数据库类型标识** | `kingbase` | 全小写，系统内部使用 |
| **显示名称** | `Kingbase` | 首字母大写，用户界面显示 |
| **默认端口** | `54321` | Kingbase数据库默认端口 |
| **Endpoint端口** | `54322` | Magnus组件监听端口（避开默认端口） |
| **协议类型** | `kingbase` | 与PostgreSQL兼容，使用postgresql模块 |
| **SSL支持** | `true` | 支持SSL连接 |
| **SSL模式** | `prefer/require/verify-ca/verify-full` | 四种SSL连接模式 |

---

## 五、执行命令

```bash
# 1. 进入项目目录
cd /Users/zhangzhongyuan/IdeaProjects/jumpserver

# 2. 创建自动化配置目录
mkdir -p apps/assets/automations/ping/database/kingbase
mkdir -p apps/assets/automations/gather_facts/database/kingbase

# 3. 创建配置文件（将上述内容复制到相应文件）

# 4. 运行数据库迁移
python apps/manage.py makemigrations
python apps/manage.py migrate

# 5. 收集静态文件（如有前端修改）
python apps/manage.py collectstatic --noinput

# 6. 重启服务
./jmsctl.sh restart

# 7. 查看日志验证
./jmsctl.sh logs
```

---

## 六、提交Git

```bash
# 添加所有修改的文件
git add apps/assets/const/database.py \
        apps/assets/const/protocol.py \
        apps/terminal/connect_methods.py \
        apps/terminal/models/component/endpoint.py \
        apps/terminal/migrations/0011_endpoint_kingbase_port.py \
        apps/assets/automations/ping/database/kingbase/ \
        apps/assets/automations/gather_facts/database/kingbase/

# 提交
git commit -m "feat: 添加Kingbase数据库支持

- 在database.py中添加Kingbase数据库类型定义
- 在protocol.py中添加kingbase协议配置，端口54321，支持SSL
- 在endpoint.py中添加kingbase_port字段，默认端口54322
- 在connect_methods.py中添加Kingbase的GUI管理支持
- 添加Kingbase数据库的ping和gather_facts自动化配置
- 生成数据库迁移文件以支持新的endpoint字段"
```

---

## 七、测试验证

### 7.1 添加Kingbase资产

1. 登录JumpServer Web界面
2. 进入 **资产管理** → **资产列表**
3. 点击 **创建** → 选择 **数据库**
4. 在 **类型** 下拉框中应该能看到 **Kingbase** 选项
5. 填写连接信息：
   - 名称：测试Kingbase
   - 地址：你的Kingbase服务器IP
   - 端口：54321（或实际端口）
   - 数据库：test
   - 用户名：system
   - 密码：你的密码

### 7.2 测试连接

1. 在资产详情页，点击 **测试连接**
2. 查看是否能成功连接
3. 查看 **资产信息** 是否正确收集到数据库版本信息

### 7.3 测试Web终端

1. 点击资产的 **连接** 按钮
2. 选择 **Web终端** 或 **客户端** 连接方式
3. 验证是否能正常打开数据库管理界面

---

## 八、注意事项

⚠️ **重要提醒：**

1. **Kingbase兼容性**：Kingbase基于PostgreSQL开发，使用`community.postgresql`模块进行连接
2. **端口冲突**：确保Endpoint端口（54322）与实际Kingbase端口（54321）不冲突
3. **SSL证书**：如果启用SSL，需要正确配置CA证书、客户端证书和密钥
4. **迁移文件依赖**：确保迁移文件的`dependencies`正确指向上一个迁移文件
5. **测试环境**：建议先在测试环境验证后再部署到生产环境

---

## 九、故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 资产类型下拉框无Kingbase | 代码未重启 | 重启JumpServer服务 |
| 连接测试失败 | 端口/密码错误 | 检查连接参数 |
| SSL连接失败 | 证书配置错误 | 检查SSL模式和证书路径 |
| Ansible执行失败 | 缺少postgresql模块 | 安装`ansible`和`community.postgresql` |
| 迁移文件报错 | 依赖关系错误 | 检查migrations的dependencies |

---

## 十、参考资源

- **HighGo提交**：`cfdbcc4dd17325f043ea5fc716aba80a022c54d9`
- **Kingbase官网**：http://www.kingbase.com.cn/
- **PostgreSQL Ansible模块**：https://docs.ansible.com/ansible/latest/collections/community/postgresql/
- **JumpServer文档**：https://docs.jumpserver.org/

---

**文档生成时间：** 2025-10-17  
**基于提交：** cfdbcc4dd (feat: 添加HighGo数据库支持)  
**适配目标：** Kingbase (人大金仓数据库)

