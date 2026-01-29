import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.star.filter.permission import PermissionType


@register("xhh_plugin", "cay", "小红花管理插件", "1.0.0")
class XhhPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        data_dir = StarTools.get_data_dir("astrbot_plugin_xhh")
        self.store_path = data_dir / "qq_store.json"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.store_path.exists():
            self.store_path.write_text('{"qq_list": {}}', encoding="utf-8")

        # 使用字典存储：qq -> 名称
        self.qq_list: dict[str, str] = {}
        self._load_store_data()

    # ================== 数据读写 ==================
    def _load_store_data(self):
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            qqs = data.get("qq_list", {})
            if isinstance(qqs, dict):
                self.qq_list = {str(k): str(v) for k, v in qqs.items()}
        except Exception as e:
            logger.error(f"xhh 数据加载失败，已重置: {e}")
            self.qq_list = {}
            self._save_store_data()

    def _save_store_data(self):
        try:
            self.store_path.write_text(
                json.dumps({"qq_list": self.qq_list}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"xhh 数据保存失败: {e}")

    # ================== 帮助指令 ==================
    @filter.command("xhh help")
    async def xhh_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "📌 小红花指令帮助\n"
            "/xhh list        查看已保存 QQ\n"
            "/xhh add 名称 QQ号    添加 QQ（管理员）\n"
            "/xhh no          查看未加入名单的群成员（管理员）"
        )

    # ================== list 指令 ==================
    @filter.command("xhh list")
    async def xhh_list(self, event: AstrMessageEvent):
        if not self.qq_list:
            yield event.plain_result("📭 当前还没有保存任何 QQ 号")
            return
        # 展示为 名称(QQ号)
        display = "\n".join(f"{name}({qq})" for qq, name in sorted(self.qq_list.items()))
        yield event.plain_result(f"📋 已保存 QQ 列表：\n{display}")

    # ================== add 指令 ==================
    @filter.command("xhh add")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_add(self, event: AstrMessageEvent):
        args = (event.message_str or "").split()
        if len(args) < 4:
            yield event.plain_result("❌ 用法：/xhh add 名称 QQ号")
            return

        name = args[2]
        qqs_to_add = [qq for qq in args[3:] if qq.isdigit()]
        if not qqs_to_add:
            yield event.plain_result("❌ QQ 号必须是纯数字")
            return

        added, skipped = [], []
        for qq in qqs_to_add:
            if qq in self.qq_list:
                skipped.append(f"{self.qq_list[qq]}({qq})")
            else:
                self.qq_list[qq] = name
                added.append(f"{name}({qq})")

        self._save_store_data()

        msg = ""
        if added:
            msg += f"✅ 已成功添加：{'，'.join(added)}\n"
        if skipped:
            msg += f"⚠️ 已存在：{'，'.join(skipped)}"

        yield event.plain_result(msg.strip())

    # ================== no 指令 ==================
    @filter.command("xhh no")
    @filter.permission_type(PermissionType.ADMIN)
    async def xhh_no(self, event: AstrMessageEvent):
        group_id = getattr(event, "group_id", None) or event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 该指令只能在群聊中使用")
            return

        bot = getattr(event, "bot", None)
        if not bot:
            yield event.plain_result("❌ 无法获取 Bot 实例")
            return

        try:
            members = await bot.get_group_member_list(group_id=group_id)
        except Exception as e:
            logger.error(f"获取群成员失败: {e}")
            yield event.plain_result("❌ 获取群成员失败，可能权限不足")
            return

        # 名称(QQ号)格式
        all_member_dict = {str(m.get("user_id")): m.get("nickname", "") for m in members if m.get("user_id")}
        not_in_list = {f"{name}({qq})" for qq, name in all_member_dict.items() if qq not in self.qq_list}

        if not not_in_list:
            yield event.plain_result("🎉 当前群所有成员都已加入小红花名单")
            return

        yield event.plain_result("📌 未加入小红花名单的成员：\n" + "\n".join(sorted(not_in_list)))

    async def terminate(self):
        logger.info("xhh 插件已卸载")
