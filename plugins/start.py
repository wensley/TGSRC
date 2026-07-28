# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

from shared_client import app
from pyrogram import filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from config import LOG_GROUP, OWNER_ID, FORCE_SUB

async def subscribe(app, message):
    return 0
     
@app.on_message(filters.command("set"))
async def set(_, message):
    if message.from_user.id not in OWNER_ID:
        await message.reply("You are not authorized to use this command.")
        return
     
    await app.set_bot_commands([
        BotCommand("start", "🚀 开始使用"),
        BotCommand("batch", "🫠 批量抓取内容"),
        BotCommand("login", "🔑 登录私有频道"),
        BotCommand("settings", "⚙️ 机器人设置"),
        BotCommand("help", "❓ 帮助信息"),
        BotCommand("stats", "📊 运行统计"),
        BotCommand("plan", "💰 订阅计划"),
        BotCommand("logout", "🚪 退出登录"),
        BotCommand("cancel", "🚫 取消当前操作")
    ])
 
    await message.reply("✅ Commands configured successfully!")
 
help_pages = [
    (
        "📝 **机器人指令一览 (1/2)**:\n\n"
        "1. **/start**\n"
        "> 启动欢迎消息与快速说明。\n\n"
        "2. **/help**\n"
        "> 显示本帮助页面（当前页）。\n\n"
        "3. **/set**\n"
        "> 管理员命令：将常用命令注册为 BotCommand（用于客户端菜单）。\n\n"
        "4. **/login**\n"
        "> 登录您的电报账号以访问私有频道的内容（通过会话字符串或手机号）。\n\n"
        "5. **/logout**\n"
        "> 注销并移除已保存的 Session。\n\n"
        "6. **/setbot [Token]** / **/rembot**\n"
        "> 保存或移除自定义机器人 Token（允许使用者绑定自己的 bot）。\n\n"
        "7. **/batch [起始链接] [结束链接]** / **/single**\n"
        "> 批量抓取与单条搬运命令，支持按链接区间搬运历史消息。\n\n"
        "8. **/dl [链接]**\n"
        "> 全网视频下载：支持 YouTube、TikTok、Instagram、Twitter/X、Facebook、Terabox、Spotify 链接等。注意：直接发送链接也会自动触发下载（无需加 `/dl`）。\n\n"
        "9. **/adl [链接]**\n"
        "> 音频提取：从视频中提取并上传 MP3（含封面与元数据）。\n\n"
        "10. **/music [关键词或链接]**\n"
        "> 音乐搜索/下载：支持关键词搜索或 Spotify 链接，下载高码率音频。\n\n"
    ),
    (
        "📝 **机器人指令一览 (2/2)**:\n\n"
        "11. **/settings**\n"
        "> 进入个人设置界面：目标群组、重命名规则、自定义 Caption、默认封面等。\n\n"
        "12. **/cancel** 或 **/stop**\n"
        "> 取消当前正在进行的登录/下载/批量任务或交互式设置。\n\n"
        "13. **/stats** 或 **/status**\n"
        "> 查看机器人或账号的当前运行状态与会话/会员信息（`/status` 为 userbot 侧命令）。\n\n"
        "14. **/plan** / **/pay**\n"
        "> 查看/购买会员计划（`/pay` 会显示可选套餐并触发支付流程）。\n\n"
        "15. **/add [user_id] [value] [unit]**\n"
        "> 管理员命令：为用户添加/续期 Premium 会籍（仅限管理员）。\n\n"
        "16. **/transfer [user_id]** / **/rem [user_id]**\n"
        "> 转让或移除 Premium（`/transfer` 将会员转给他人，`/rem` 管理员移除）。\n\n"
        "🔧 **进阶与设置说明 (/settings)**:\n"
        "- **设置目标群组:** 在设置中使用 `设置目标群组 ID` 输入一个或多个目标（支持 -100 前缀与 /话题ID）。\n"
        "- **重命名/替换规则:** 可在设置中配置文件名后缀、替换或删除关键词。\n"
        "- **默认封面:** 上传一张图片以作为以后下载视频的默认封面。\n\n"
        "📌 **备注:**\n"
        "- 机器人支持直接发送社交网络链接自动识别并开始下载（无需 `/dl` 命令）。\n"
        "- 某些命令仅在私聊中可用（如登录、支付、设置）。\n"
        "- 如需取消交互式操作，请发送 `/cancel`。\n\n"
    )
]
 
async def send_or_edit_help_page(_, message, page_number):
    if page_number < 0 or page_number >= len(help_pages):
        return
     
    prev_button = InlineKeyboardButton("◀️ 上一页", callback_data=f"help_prev_{page_number}")
    next_button = InlineKeyboardButton("下一页 ▶️", callback_data=f"help_next_{page_number}")
     
    buttons = []
    if page_number > 0:
        buttons.append(prev_button)
    if page_number < len(help_pages) - 1:
        buttons.append(next_button)
     
    keyboard = InlineKeyboardMarkup([buttons])
     
    await message.delete()
     
    await message.reply(
        help_pages[page_number],
        reply_markup=keyboard
    )
 
@app.on_message(filters.command("help"))
async def help(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return
     
    await send_or_edit_help_page(client, message, 0)
 
@app.on_callback_query(filters.regex(r"help_(prev|next)_(\d+)"))
async def on_help_navigation(client, callback_query):
    action, page_number = callback_query.data.split("_")[1], int(callback_query.data.split("_")[2])
 
    if action == "prev":
        page_number -= 1
    elif action == "next":
        page_number += 1

    await send_or_edit_help_page(client, callback_query.message, page_number)
     
    await callback_query.answer()
 
@app.on_message(filters.command("terms") & filters.private)
async def terms(client, message):
    terms_text = (
        "> 📜 **Terms and Conditions** 📜\n\n"
        "✨ We are not responsible for user deeds, and we do not promote copyrighted content. If any user engages in such activities, it is solely their responsibility.\n"
        "✨ Upon purchase, we do not guarantee the uptime, downtime, or the validity of the plan. __Authorization and banning of users are at our discretion; we reserve the right to ban or authorize users at any time.__\n"
        "✨ Payment to us **__does not guarantee__** authorization for the /batch command. All decisions regarding authorization are made at our discretion and mood.\n"
    )
    await message.reply_text(terms_text)
 
@app.on_message(filters.command("plan") & filters.private)
async def plan(client, message):
    await message.reply_text("💎 使用 /pay 查看 Telegram Stars 订阅套餐。")
  
@app.on_callback_query(filters.regex("see_plan"))
async def see_plan(client, callback_query):
    await callback_query.message.edit_text("💎 使用 /pay 查看 Telegram Stars 订阅套餐。")
  
@app.on_callback_query(filters.regex("see_terms"))
async def see_terms(client, callback_query):
    await callback_query.message.edit_text(
        "> 📜 **Terms and Conditions** 📜\n\n"
        "We are not responsible for user deeds, and we do not promote copyrighted content.\n"
        "All decisions regarding authorization are at our discretion."
    )

