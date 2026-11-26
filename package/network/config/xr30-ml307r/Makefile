# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk

PKG_NAME:=xr30-ml307r
PKG_RELEASE:=3
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/xr30-ml307r
  SECTION:=net
  CATEGORY:=Network
  TITLE:=XR30 ML307R and HandsomeMod USB Ethernet uplink defaults
  DEPENDS:=@TARGET_mediatek_filogic +kmod-usb-net-cdc-ether +kmod-usb-net-rndis +odhcp6c +ucode-mod-uci +ucode-mod-ubus +ucode-mod-fs
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/xr30-ml307r/install
	$(INSTALL_DIR) $(1)/etc/uci-defaults $(1)/etc/init.d $(1)/etc/hotplug.d/net $(1)/usr/libexec
	$(INSTALL_BIN) ./files/defaults $(1)/etc/uci-defaults/90-xr30-ml307r
	$(INSTALL_BIN) ./files/init $(1)/etc/init.d/xr30-ml307r
	$(INSTALL_DATA) ./files/hotplug $(1)/etc/hotplug.d/net/15-xr30-ml307r
	$(INSTALL_BIN) ./files/name-device $(1)/usr/libexec/xr30-name-ml307r
	$(INSTALL_BIN) ./files/cellular6.uc $(1)/usr/libexec/xr30-cellular6
	$(INSTALL_DIR) $(1)/etc/hotplug.d/iface
	$(INSTALL_DATA) ./files/iface $(1)/etc/hotplug.d/iface/99-xr30-cellular6
endef

$(eval $(call BuildPackage,xr30-ml307r))
