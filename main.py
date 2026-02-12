import json
import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.star.filter.permission import PermissionType
import astrbot.api.message_components as Comp
import aiohttp
from urllib.parse import urlencode
@register("astrbot_plugin_xhh_manager", "cay", "小红花管理插件", "1.0.0")
class XhhPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 数据目录 & 文件
        data_dir = StarTools.get_data_dir("astrbot_plugin_xhh")
        self.store_path = data_dir / "qq_store.json"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.store_path.exists():
            self.store_path.write_text("{}", encoding="utf-8")

        # 当前群的 QQ 数据
        self.qq_list: dict[str, str] = {}
        self.current_group_id: str | None = None

    # ================== 数据读写 ==================
    def _load_store_data(self, group_id: str):
        """按群加载 QQ 数据"""
        self.current_group_id = group_id
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            group_data = data.get(group_id, {}).get("qq_list", {})
            self.qq_list = {str(k): str(v) for k, v in group_data.items()}
        except Exception:
            self.qq_list = {}

    def _save_store_data(self):
        """保存当前群的 QQ 数据"""
        if not self.current_group_id:
            return

        try:
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}

            data[self.current_group_id] = {"qq_list": self.qq_list}
            self.store_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"xhh 数据保存失败: {e}")

    # ================== 帮助指令 ==================
    @filter.command("xhh help")
    async def xhh_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            """📋 小红花管理插件帮助
    --------------------
/xhh list        查看已保存 QQ
/xhh at          艾特未加入名单的群成员
/xhh has QQ号    查看指定QQ是否已添加
/xhh del QQ号    删除 QQ（管理员）
/xhh add QQ号    添加 QQ（管理员）
/xhh no          查看未加入名单的群成员（管理员）"""
        )

    # ================== list 指令 ==================
    @filter.command("xhh list")
    async def xhh_list(self, event: AstrMessageEvent):
        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)

        if not self.qq_list:
            yield event.plain_result("📭 当前还没有保存任何 QQ 号")
            return

        display = "\n".join(f"{name}({qq})" for qq, name in sorted(self.qq_list.items()))
        yield event.plain_result(f"📋 已保存 QQ 列表：\n{display}")

    # ================== add 指令 ==================
    @filter.command("xhh add")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_add(self, event: AstrMessageEvent):
        args = (event.message_str or "").split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/xhh add QQ号 [QQ号...]")
            return

        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)

        bot = getattr(event, "bot", None)
        if not bot:
            yield event.plain_result("❌ 无法获取 Bot 实例")
            return

        # ① 获取当前群成员 QQ 列表
        try:
            members = await bot.get_group_member_list(group_id=int(group_id))
            group_member_map = {
                str(m.get("user_id")): m.get("nickname", "未知")
                for m in members
                if m.get("user_id")
            }
        except Exception as e:
            logger.error(f"获取群成员失败: {e}")
            yield event.plain_result("❌ 获取群成员失败，可能权限不足")
            return

        added, skipped, not_in_group = [], [], []

        # ② 校验 QQ
        for qq in args[2:]:
            if not qq.isdigit():
                continue

            if qq not in group_member_map:
                not_in_group.append(qq)
                continue

            if qq in self.qq_list:
                skipped.append(f"{self.qq_list[qq]}({qq})")
                continue

            name = group_member_map.get(qq, "未知")
            self.qq_list[qq] = name
            added.append(f"{name}({qq})")

        self._save_store_data()

        # ③ 结果汇总
        msg = ""
        if added:
            msg += f"✅ 已成功添加：{'，'.join(added)}\n"
        if skipped:
            msg += f"⚠️ 已存在：{'，'.join(skipped)}\n"
        if not_in_group:
            msg += f"❌ 不在本群，未添加：{'，'.join(not_in_group)}"

        yield event.plain_result(msg.strip())
    # ================== no 指令 ==================
    @filter.command("xhh no")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_no(self, event: AstrMessageEvent):
        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)
    
        bot = getattr(event, "bot", None)
        if not bot:
            yield event.plain_result("❌ 无法获取 Bot 实例")
            return
    
        try:
            members = await bot.get_group_member_list(group_id=int(group_id))
        except Exception as e:
            logger.error(f"获取群成员失败: {e}")
            yield event.plain_result("❌ 获取群成员失败，可能权限不足")
            return
    
        bot_qq = str(getattr(event, "self_id", None) or getattr(bot, "self_id", ""))  # 机器人的 QQ
        all_member_dict = {
            str(m.get("user_id")): m.get("nickname", "")
            for m in members
            if m.get("user_id") and str(m.get("user_id")) != bot_qq  # 排除机器人自己
        }
    
        not_in_list = {f"{name}({qq})" for qq, name in all_member_dict.items() if qq not in self.qq_list}
    
        if not not_in_list:
            yield event.plain_result("🎉 当前群所有成员都已加入小红花名单")
            return
    
        yield event.plain_result("📌 未加入小红花名单的成员：\n" + "\n".join(sorted(not_in_list)))

    # ================== del 指令 ==================
    @filter.command("xhh del")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_del(self, event: AstrMessageEvent):
        args = (event.message_str or "").split()
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/xhh del QQ号")
            return

        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)

        removed, not_found = [], []

        for qq in args[2:]:
            if not qq.isdigit():
                continue

            if qq in self.qq_list:
                name = self.qq_list.pop(qq)
                removed.append(f"{name}({qq})")
            else:
                not_found.append(qq)

        if removed:
            self._save_store_data()

        msg = ""
        if removed:
            msg += f"🗑️ 已删除：{'，'.join(removed)}\n"
        if not_found:
            msg += f"⚠️ 未找到：{'，'.join(not_found)}"

        yield event.plain_result(msg.strip())

    # ================== has 指令 ==================
    @filter.command("xhh has")
    async def xhh_has(self, event: AstrMessageEvent):
        args = (event.message_str or "").split()
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/xhh has QQ号")
            return

        qq = args[2] if len(args) > 2 else None
        if not qq or not qq.isdigit():
            yield event.plain_result("❌ 请提供正确的 QQ 号")
            return

        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)

        if qq in self.qq_list:
            name = self.qq_list[qq]
            yield event.plain_result(f"✅ {name}({qq}) 已在小红花名单中")
        else:
            yield event.plain_result(f"❌ QQ({qq}) 不在小红花名单中")
    # ================== at 指令 ==================
    @filter.command("xhh at")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_at(self, event: AstrMessageEvent):
        group_id = str(event.get_group_id())
        self._load_store_data(group_id)

        bot = getattr(event, "bot", None)
        if not bot:
            yield event.plain_result("❌ 无法获取 Bot 实例")
            return

        try:
            members = await bot.get_group_member_list(group_id=int(group_id))
        except Exception as e:
            logger.error(f"获取群成员失败: {e}")
            yield event.plain_result("❌ 获取群成员失败")
            return

        bot_qq = str(event.get_self_id())

        # 找出未加入名单的 QQ
        not_in_list = [
            str(m["user_id"])
            for m in members
            if m.get("user_id")
            and str(m["user_id"]) != bot_qq
            and str(m["user_id"]) not in self.qq_list
        ]

        if not not_in_list:
            yield event.plain_result("🎉 当前群所有成员都已加入小红花名单")
            return

        # 🔥 组合文字 + @
        chain = [Comp.Plain("📢 以下成员尚未加入小红花名单：\n")]
        for qq in not_in_list[:10]:  # 限制数量，防风控
            chain.append(Comp.At(qq=int(qq)))

        # 先发送文字+@列表
        yield event.chain_result(chain)

        # 发送固定图片 qrcode.jpg
        current_dir = os.path.dirname(__file__)
        image_path = os.path.join(current_dir, "qrcode.jpg")
        pic1_path = os.path.join(current_dir, "pic_1.jpg")
        pic2_path = os.path.join(current_dir, "pic_2.jpg")
        if os.path.exists(image_path):
            yield event.image_result(image_path)
            yield event.plain_result("扫码后发送下面两张示例图片")
            yield event.image_result(pic1_path)
            yield event.image_result(pic2_path)
            
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.command("xhh valid", only_private=True)
    async def xhh_validate(self, event: AstrMessageEvent):
        qq = str(event.message_obj.sender.user_id)
        if not qq:
            yield event.plain_result("❌ 无法获取 QQ 号")
            return
        current_dir = os.path.dirname(__file__)
        image_path = os.path.join(current_dir, "qrcode.jpg")
        pic1_path = os.path.join(current_dir, "pic_1.jpg")
        pic2_path = os.path.join(current_dir, "pic_2.jpg")
        if os.path.exists(image_path):
            yield event.image_result(image_path)
            yield event.plain_result("扫码后发送下面两张示例图片")
            yield event.image_result(pic1_path)
            yield event.image_result(pic2_path)
    # ================== migrate 指令 ==================
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("xhh migrate")
    async def xhh_migrate(self, event: AstrMessageEvent):
        """
        迁移 QQ 数据：从源群迁移到目标群，仅迁移两个群都存在的 QQ。
        用法: /xhh migrate 源群号 目标群号
        """
        args = (event.message_str or "").split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/xhh migrate 源群号 目标群号")
            return

        src_group_id = args[2]
        dst_group_id = args[3]

        bot = getattr(event, "bot", None)
        if not bot:
            yield event.plain_result("❌ 无法获取 Bot 实例")
            return

        # ① 加载源群 QQ 数据
        self._load_store_data(src_group_id)
        src_qq_list = self.qq_list.copy()
        if not src_qq_list:
            yield event.plain_result(f"❌ 源群 {src_group_id} 没有 QQ 数据")
            return

        # ② 获取目标群成员列表
        try:
            dst_members = await bot.get_group_member_list(group_id=int(dst_group_id))
            dst_member_map = {str(m["user_id"]): m.get("nickname", "未知") for m in dst_members if m.get("user_id")}
        except Exception as e:
            logger.error(f"获取目标群成员失败: {e}")
            yield event.plain_result(f"❌ 获取目标群 {dst_group_id} 成员失败")
            return

        # ③ 获取源群成员列表（仅用于校验是否存在目标群）
        try:
            src_members = await bot.get_group_member_list(group_id=int(src_group_id))
            src_member_set = {str(m["user_id"]) for m in src_members if m.get("user_id")}
        except Exception as e:
            logger.error(f"获取源群成员失败: {e}")
            yield event.plain_result(f"❌ 获取源群 {src_group_id} 成员失败")
            return

        # ④ 迁移：只迁移两个群都存在的 QQ
        migrated = []
        self._load_store_data(dst_group_id)  # 切换到目标群
        for qq, name in src_qq_list.items():
            if qq in src_member_set and qq in dst_member_map:
                self.qq_list[qq] = dst_member_map.get(qq, name)
                migrated.append(f"{self.qq_list[qq]}({qq})")

        if migrated:
            self._save_store_data()
            yield event.plain_result(f"✅ 成功迁移 {len(migrated)} 个 QQ 到目标群 {dst_group_id}：\n" + "\n".join(migrated))
        else:
            yield event.plain_result("⚠️ 没有 QQ 可以迁移（可能目标群未包含源群成员）")
    async def terminate(self):
        logger.info("xhh 插件已卸载")
