import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from discord.ui import Button, View
import aiohttp

BACKEND_URL_REGISTER = 'http://192.168.65.232:3000/api/register'
BACKEND_URL_VOTE = "http://192.168.65.232:3000/api/vote"
BACKEND_URL_SUGGESTION = "http://192.168.65.232:3000/api/suggestion"

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
intents = discord.Intents.all()  # 開啟機器人所有權限
bot = commands.Bot(command_prefix="$", intents=intents)

# register_________________________________________________________________________
@bot.event
async def on_ready():
    slash = await bot.tree.sync()  # 讓 Bot 的斜線指令可以同步到 Discord 上
    print(f"目前登入身份 --> {bot.user}")
    print(f"載入 {len(slash)} 個斜線指令")

@bot.event
async def on_member_join(member):
    user_id = member.id  # 獲取用戶 ID
    user_id = int(user_id) 
    user_id = str(user_id)
    print(user_id)
    # 私訊歡迎訊息
    await member.create_dm()
    await member.dm_channel.send(f'Hi {member.name}, 歡迎加入SITCON 大學!')

    # 問編號和姓名並將其加入相應的身分組
    await member.dm_channel.send("請輸入編號:")

    def check(m):
        return m.author == member and m.channel == member.dm_channel

    try:
        student_id_msg = await bot.wait_for('message', check=check, timeout=60)
        student_id = student_id_msg.content
        await member.dm_channel.send("請輸入姓名:")
        name_msg = await bot.wait_for('message', check=check, timeout=60)
        name = name_msg.content

        await member.dm_channel.send(f"歡迎，{name}！")
        view = RoleAssignmentView(member, user_id, student_id, name)
        await member.dm_channel.send("你是學生還是教職員呢？", view=view)

    except asyncio.TimeoutError:
        await member.dm_channel.send("超時未回應，請重新輸入 !register 指令開始註冊。")

# register-身分組___________________________________________________________________________
class RoleAssignmentView(View):
    def __init__(self, member, user_id, student_id, name):
        super().__init__()
        self.member = member
        self.user_id = user_id
        self.student_id = student_id
        self.name = name
        self.selected_role = None

    @discord.ui.button(label="教職員", style=discord.ButtonStyle.primary)
    async def school_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = discord.utils.get(bot.guilds, id=int(GUILD_ID))
        if guild is None:
            await interaction.response.send_message("無法找到伺服器。", ephemeral=True)
            return
        role_name = "教職員"
        role = discord.utils.get(guild.roles, name=role_name)
        await self.member.add_roles(role)
        await interaction.response.send_message("你已加入教職員組！", ephemeral=True)
        self.selected_role = role_name
        try:
            await interaction.message.delete()
        except discord.errors.NotFound:
            pass

        await self.send_registration_to_backend(interaction)
     
    @discord.ui.button(label="學生", style=discord.ButtonStyle.primary)
    async def student_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = discord.utils.get(bot.guilds, id=int(GUILD_ID))
        if guild is None:
            await interaction.response.send_message("無法找到伺服器。", ephemeral=True)
            return
        role_name = "學生"
        role = discord.utils.get(guild.roles, name=role_name)
        await self.member.add_roles(role)
        await interaction.response.send_message("你已加入學生組！", ephemeral=True)
        self.selected_role = role_name 
        try:
            await interaction.message.delete()
        except discord.errors.NotFound:
            pass

        await self.send_registration_to_backend(interaction)       
     
    async def send_registration_to_backend(self, interaction):
        if self.student_id and self.name and self.selected_role:
            async with aiohttp.ClientSession() as session:
                data = {
                    "dc_id": self.user_id,
                    "student_id": self.student_id,
                    "name": self.name,
                    "role": self.selected_role
                }
                async with session.post(BACKEND_URL_REGISTER, json=data) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message(content="註冊失敗，請稍後再試。")
                    
@bot.tree.command(name="re-register", description="重新註冊")
async def re_register(interaction: discord.Interaction):
    # 如果發送在公共頻道
    if not isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("請聯繫管理員。")
        return
    try:
        await interaction.response.send_message("請輸入編號:", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        student_id_msg = await bot.wait_for('message', check=check, timeout=60)
        student_id = student_id_msg.content
        
        await interaction.followup.send("請輸入姓名:", ephemeral=True)
        name_msg = await bot.wait_for('message', check=check, timeout=60)
        name = name_msg.content

        guild = discord.utils.get(bot.guilds, id=int(GUILD_ID))
        if guild is None:
            await interaction.followup.send("無法找到伺服器。", ephemeral=True)
            return
        member = guild.get_member(interaction.user.id)
        
        await interaction.followup.send(f"歡迎，{name}！", ephemeral=True)
        view = RoleAssignmentView(member, interaction.user.id, student_id, name)
        await interaction.followup.send("你是學生還是教職員呢？", view=view, ephemeral=True)

    except asyncio.TimeoutError:
        await interaction.followup.send("超時未回應，請重新輸入 !register 指令開始註冊。", ephemeral=True)


# vote________________________________________________________________________________
async def button_callback(interaction: discord.Interaction):
    dc_id = interaction.user.id  # 獲取用戶 ID
    print(dc_id)
    vote_result = interaction.data.get("custom_id")
    await interaction.message.delete()
    data = {
        "dc_id": dc_id,
        "vote_result": vote_result
    }
    async with aiohttp.ClientSession() as session:
        BACKEND_URL_VOTE_DEF = "{}/{}/{}".format(BACKEND_URL_VOTE, dc_id, vote_result)
        print(BACKEND_URL_VOTE_DEF)
        async with session.post(BACKEND_URL_VOTE_DEF, json=data) as resp:
            if resp.status == 200:
                await interaction.response.send_message(content="投票完成!")
            else:
                print(resp)
                await interaction.response.send_message(content="投票失敗，請稍後再試。")

@bot.tree.command(name="vote", description="學生會長選舉")
async def vote(interaction: discord.Interaction):
    try:
        view = discord.ui.View()

        button1 = discord.ui.Button(
            label="林慕白",
            style=discord.ButtonStyle.blurple,
            row=0,
            custom_id="0"
        )
        button2 = discord.ui.Button(
            label="周若雪",
            style=discord.ButtonStyle.green,
            row=0,
            custom_id="1"
        )
        button3 = discord.ui.Button(
            label="許雲溪",
            style=discord.ButtonStyle.red,
            row=0,
            custom_id="2"
        )
        button4 = discord.ui.Button(
            label="政見對決",
            style=discord.ButtonStyle.link,
            url=f"http://192.168.65.232:4200/?id={interaction.user.id}",
            row=2
        )
        button5 = discord.ui.Button(
            label="候選人政見",
            style=discord.ButtonStyle.link,
            url=f"http://192.168.65.232:4201/",
            row=2
        )

        button1.callback = button_callback
        button2.callback = button_callback
        button3.callback = button_callback

        view.add_item(button1)
        view.add_item(button2)
        view.add_item(button3)

        view.add_item(discord.ui.Button(
            label="\u2B07 還沒想好嗎? 做個測驗吧!",
            style=discord.ButtonStyle.grey,
            disabled=True,
            row=1
        ))

        view.add_item(button4)
        view.add_item(button5)

        await interaction.response.send_message(view=view)

    except asyncio.TimeoutError:
        await interaction.send("超時未回應，請重新輸入指令進行投票。")

# suggestion box_________________________________________________________________________
@bot.tree.command(name="suggestionbox", description="匿名建議箱")
async def suggestion(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("請輸入您的建議:", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        suggestion_msg = await bot.wait_for('message', check=check, timeout=600)
        suggestion_text = suggestion_msg.content
        
        async with aiohttp.ClientSession() as session:
            async with session.post(BACKEND_URL_SUGGESTION, json={"suggestion": suggestion_text}) as resp:
                if resp.status == 200:
                    await interaction.followup.send("已經匿名放入建議箱!", ephemeral=True)
                else:
                    await interaction.followup.send("建議失敗，請稍後再試。", ephemeral=True)

    except asyncio.TimeoutError:
        await interaction.followup.send("超時未回應，請重新輸入指令進行建議。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"發生錯誤：{e}", ephemeral=True)



bot.run(DISCORD_TOKEN)