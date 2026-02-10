################################################################################
#
# buildroot-agent
#
################################################################################

BUILDROOT_AGENT_VERSION = 1.0.0
BUILDROOT_AGENT_SITE = $(TOPDIR)/../buildroot-agent
BUILDROOT_AGENT_SITE_METHOD = local
BUILDROOT_AGENT_LICENSE = MIT
BUILDROOT_AGENT_LICENSE_FILES = LICENSE

BUILDROOT_AGENT_DEPENDENCIES = libwebsockets openssl

# 编译选项
BUILDROOT_AGENT_MAKE_OPTS = \
	CC="$(TARGET_CC)" \
	STRIP="$(TARGET_STRIP)" \
	CFLAGS="$(TARGET_CFLAGS) -I$(STAGING_DIR)/usr/include" \
	LDFLAGS="$(TARGET_LDFLAGS) -L$(STAGING_DIR)/usr/lib"

define BUILDROOT_AGENT_BUILD_CMDS
	$(MAKE) $(BUILDROOT_AGENT_MAKE_OPTS) -C $(@D) clean
	$(MAKE) $(BUILDROOT_AGENT_MAKE_OPTS) -C $(@D) all
endef

define BUILDROOT_AGENT_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/bin/buildroot-agent \
		$(TARGET_DIR)/usr/bin/buildroot-agent
	
	# 安装配置文件
	$(INSTALL) -D -m 0644 $(@D)/scripts/agent.conf.sample \
		$(TARGET_DIR)/etc/agent/agent.conf
	
	# 安装启动脚本
	$(INSTALL) -D -m 0755 $(@D)/scripts/S99agent \
		$(TARGET_DIR)/etc/init.d/S99agent
endef

# 生成默认配置
define BUILDROOT_AGENT_INSTALL_INIT_SYSV
	# 创建必要目录
	mkdir -p $(TARGET_DIR)/etc/agent
	mkdir -p $(TARGET_DIR)/tmp/agent_scripts
	mkdir -p $(TARGET_DIR)/var/log
endef

$(eval $(generic-package))
