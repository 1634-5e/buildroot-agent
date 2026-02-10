# Buildroot Agent Makefile
# 用于交叉编译嵌入式Agent程序

# 项目信息
PROJECT := buildroot-agent
VERSION := 1.0.0

# 目录结构
SRCDIR := src
INCDIR := include
OBJDIR := obj
BINDIR := bin

# 源文件
SOURCES := $(wildcard $(SRCDIR)/*.c)
OBJECTS := $(patsubst $(SRCDIR)/%.c,$(OBJDIR)/%.o,$(SOURCES))

# 目标文件
TARGET := $(BINDIR)/$(PROJECT)

# 编译器设置 (可通过环境变量覆盖，用于交叉编译)
CC ?= gcc
STRIP ?= strip

# 编译选项
CFLAGS := -Wall -Wextra -O2 -g
CFLAGS += -I$(INCDIR)
CFLAGS += -D_GNU_SOURCE
CFLAGS += -DVERSION=\"$(VERSION)\"

# 链接选项
LDFLAGS := -pthread
LIBS := -lwebsockets -lssl -lcrypto -lutil

# 调试模式
ifdef DEBUG
    CFLAGS := -Wall -Wextra -O0 -g3 -DDEBUG
endif

# 静态链接 (用于某些嵌入式环境)
ifdef STATIC
    LDFLAGS += -static
endif

# 默认目标
.PHONY: all
all: dirs $(TARGET)

# 创建目录
.PHONY: dirs
dirs:
	@mkdir -p $(OBJDIR) $(BINDIR)

# 链接目标
$(TARGET): $(OBJECTS)
	@echo "  LD      $@"
	@$(CC) $(LDFLAGS) -o $@ $^ $(LIBS)
	@echo "编译完成: $@"

# 编译源文件
$(OBJDIR)/%.o: $(SRCDIR)/%.c
	@echo "  CC      $<"
	@$(CC) $(CFLAGS) -c -o $@ $<

# 安装
.PHONY: install
install: $(TARGET)
	@echo "安装到 $(DESTDIR)/usr/bin/"
	@mkdir -p $(DESTDIR)/usr/bin
	@mkdir -p $(DESTDIR)/etc/agent
	@mkdir -p $(DESTDIR)/etc/init.d
	@cp $(TARGET) $(DESTDIR)/usr/bin/
	@cp scripts/agent.conf.sample $(DESTDIR)/etc/agent/agent.conf 2>/dev/null || true
	@cp scripts/S99agent $(DESTDIR)/etc/init.d/ 2>/dev/null || true
	@chmod 755 $(DESTDIR)/usr/bin/$(PROJECT)
	@echo "安装完成"

# 卸载
.PHONY: uninstall
uninstall:
	@rm -f $(DESTDIR)/usr/bin/$(PROJECT)
	@rm -rf $(DESTDIR)/etc/agent
	@rm -f $(DESTDIR)/etc/init.d/S99agent
	@echo "卸载完成"

# 清理
.PHONY: clean
clean:
	@rm -rf $(OBJDIR) $(BINDIR)
	@echo "清理完成"

# 发布版本 (strip符号表)
.PHONY: release
release: $(TARGET)
	@echo "生成发布版本..."
	@$(STRIP) $(TARGET)
	@ls -lh $(TARGET)

# 打包
.PHONY: package
package: release
	@echo "打包..."
	@mkdir -p dist
	@tar czvf dist/$(PROJECT)-$(VERSION).tar.gz \
		-C $(BINDIR) $(PROJECT) \
		-C ../scripts agent.conf.sample S99agent 2>/dev/null || \
		tar czvf dist/$(PROJECT)-$(VERSION).tar.gz -C $(BINDIR) $(PROJECT)
	@echo "打包完成: dist/$(PROJECT)-$(VERSION).tar.gz"

# 显示帮助
.PHONY: help
help:
	@echo "Buildroot Agent 编译系统"
	@echo ""
	@echo "用法: make [目标] [选项]"
	@echo ""
	@echo "目标:"
	@echo "  all       - 编译项目 (默认)"
	@echo "  clean     - 清理编译文件"
	@echo "  install   - 安装到系统"
	@echo "  uninstall - 从系统卸载"
	@echo "  release   - 生成发布版本 (strip)"
	@echo "  package   - 打包发布"
	@echo "  help      - 显示此帮助"
	@echo ""
	@echo "选项:"
	@echo "  DEBUG=1   - 调试模式编译"
	@echo "  STATIC=1  - 静态链接"
	@echo "  CC=...    - 指定编译器 (交叉编译)"
	@echo "  DESTDIR=  - 安装目标目录"
	@echo ""
	@echo "交叉编译示例:"
	@echo "  make CC=arm-linux-gnueabihf-gcc STRIP=arm-linux-gnueabihf-strip"
	@echo ""

# 依赖关系
$(OBJDIR)/agent_main.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_websocket.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_status.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_log.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_script.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_pty.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_protocol.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_config.o: $(INCDIR)/agent.h
$(OBJDIR)/agent_util.o: $(INCDIR)/agent.h
