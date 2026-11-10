-- =============================================================================
-- 考研 AI 导学平台 · 鉴权与授权建表脚本(MySQL 8.0)
--
-- 由 SQLAlchemy 模型直接导出, 与 app/models 下的定义逐字对应, 不手写。
-- 用法:  mysql -uroot -p kaoyan < rbac_mysql.sql
-- 范围:  《权限表》五张权限表 + 用户画像表 user_account(ER 图登录配套)
--        + 审计日志表 sys_audit_log(禅道式操作留痕, 权限表本身没有)。
--        school_info / study_plan / exam_* 等业务表属于其他模块, 本次不建。
-- 字符集: 统一 utf8mb4 / utf8mb4_general_ci, 避免中文昵称与注释乱码。
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;


CREATE TABLE sys_audit_log (
	id BIGINT NOT NULL COMMENT '日志编号' AUTO_INCREMENT, 
	user_id BIGINT COMMENT '操作者 user_id, 登录失败等场景为空', 
	login_name VARCHAR(50) COMMENT '操作者登录名', 
	action VARCHAR(50) NOT NULL COMMENT '动作标识, 如 role.create / login.failure', 
	target_type VARCHAR(30) COMMENT '目标类型, 如 role/user/session', 
	target_id VARCHAR(50) COMMENT '目标编号', 
	detail JSON COMMENT '变更详情, 只放前后差异, 不留密码等敏感值', 
	ip VARCHAR(64) COMMENT '来源 IP', 
	success BOOL NOT NULL COMMENT '是否成功' DEFAULT 1, 
	create_time DATETIME NOT NULL COMMENT '操作时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE sys_permission (
	perm_id BIGINT NOT NULL COMMENT '权限唯一编号' AUTO_INCREMENT, 
	perm_key VARCHAR(80) NOT NULL COMMENT '权限标识符, 格式为 模块:操作, 如 studyplan:add', 
	perm_name VARCHAR(100) NOT NULL COMMENT '权限中文名称', 
	module_name VARCHAR(50) NOT NULL COMMENT '所属业务模块, 后台按它分组展示', 
	PRIMARY KEY (perm_id), 
	UNIQUE (perm_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE sys_role (
	role_id BIGINT NOT NULL COMMENT '角色唯一编号' AUTO_INCREMENT, 
	role_name VARCHAR(30) NOT NULL COMMENT '角色名称, 不可重复', 
	role_desc VARCHAR(200) COMMENT '角色功能描述', 
	PRIMARY KEY (role_id), 
	UNIQUE (role_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE sys_user (
	user_id BIGINT NOT NULL COMMENT '登录账号唯一编号' AUTO_INCREMENT, 
	login_name VARCHAR(50) NOT NULL COMMENT '登录用户名', 
	email VARCHAR(120) NOT NULL COMMENT '绑定邮箱, 用于邮箱验证码登录与找回密码', 
	password VARCHAR(128) NOT NULL COMMENT 'argon2 加密串, 禁止明文', 
	account_status TINYINT NOT NULL COMMENT '账号状态: 0 禁用, 1 启用' DEFAULT '1', 
	create_time DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE sys_role_permission (
	id BIGINT NOT NULL COMMENT '中间记录主键' AUTO_INCREMENT, 
	role_id BIGINT NOT NULL, 
	perm_id BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_role_perm UNIQUE (role_id, perm_id), 
	FOREIGN KEY(role_id) REFERENCES sys_role (role_id) ON DELETE CASCADE, 
	FOREIGN KEY(perm_id) REFERENCES sys_permission (perm_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE sys_user_role (
	id BIGINT NOT NULL COMMENT '中间记录主键' AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	role_id BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_user_role UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES sys_user (user_id) ON DELETE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES sys_role (role_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE user_account (
	user_id BIGINT NOT NULL COMMENT '学生业务主键, 关联 sys_user.user_id', 
	user_name VARCHAR(50) NOT NULL COMMENT '用户昵称(原 nickname)', 
	undergraduate_major VARCHAR(60) COMMENT '本科专业', 
	target_area VARCHAR(30) COMMENT '目标报考地区', 
	target_school_id BIGINT COMMENT '目标院校编号, 由择校模块的院校主表提供', 
	prep_stage VARCHAR(20) COMMENT '备考阶段', 
	base_level JSON COMMENT '各科目基础水平, 形如 {科目: 等级}', 
	remain_days INTEGER COMMENT '备考剩余天数', 
	target_score INTEGER COMMENT '目标考试分数', 
	digital_person_mode VARCHAR(20) COMMENT '数字人教学模式', 
	create_time DATETIME NOT NULL COMMENT '账号创建时间' DEFAULT CURRENT_TIMESTAMP, 
	major VARCHAR(100) COMMENT '报考专业名称(原 target_major)', 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES sys_user (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

SET FOREIGN_KEY_CHECKS = 1;
