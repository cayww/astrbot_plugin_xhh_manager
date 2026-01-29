import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.star.filter.permission import PermissionType


@register("xhh_plugin", "cay", "小红花管理插件", "1.0.0")
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
            "📌 小红花指令帮助\n"
            "/xhh list        查看已保存 QQ\n"
            "/xhh add 名称 QQ号    添加 QQ（管理员）\n"
            "/xhh no          查看未加入名单的群成员（管理员）"
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
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/xhh add 名称 QQ号 或 /xhh add QQ号")
            return

        group_id = str(getattr(event, "group_id", None) or event.get_group_id())
        self._load_store_data(group_id)

        bot = getattr(event, "bot", None)
        added, skipped = [], []

        for qq in args[2:]:
            if not qq.isdigit():
                continue

            if qq in self.qq_list:
                skipped.append(f"{self.qq_list[qq]}({qq})")
                continue

            # 尝试自动获取名称
            name = "未知"
            if bot:
                try:
                    member = await bot.get_group_member_info(group_id=int(group_id), user_id=int(qq))
                    name = member.get("nickname", "未知") if member else "未知"
                except Exception:
                    name = "未知"

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

        all_member_dict = {str(m.get("user_id")): m.get("nickname", "") for m in members if m.get("user_id")}
        not_in_list = {f"{name}({qq})" for qq, name in all_member_dict.items() if qq not in self.qq_list}

        if not not_in_list:
            yield event.plain_result("🎉 当前群所有成员都已加入小红花名单")
            return

        yield event.plain_result("📌 未加入小红花名单的成员：\n" + "\n".join(sorted(not_in_list)))

    async def terminate(self):
        logger.info("xhh 插件已卸载")
