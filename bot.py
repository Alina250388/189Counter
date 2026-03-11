import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8755685024:AAHbEJZqUOMDwkCsJ3BGybcJ2_766WbtdMQ"

conn = sqlite3.connect("debts.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS debts (
debtor TEXT,
creditor TEXT,
amount REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
id INTEGER PRIMARY KEY AUTOINCREMENT,
payer TEXT,
item TEXT,
amount REAL,
participants TEXT,
share REAL
)
""")

conn.commit()


def normalize(debtor, creditor, amount):

    if debtor == creditor:
        return

    cursor.execute(
        "SELECT amount FROM debts WHERE debtor=? AND creditor=?",
        (creditor, debtor)
    )

    reverse = cursor.fetchone()

    if reverse:

        if reverse[0] > amount:

            cursor.execute(
                "UPDATE debts SET amount=? WHERE debtor=? AND creditor=?",
                (reverse[0] - amount, creditor, debtor)
            )

        elif reverse[0] < amount:

            cursor.execute(
                "DELETE FROM debts WHERE debtor=? AND creditor=?",
                (creditor, debtor)
            )

            cursor.execute(
                "INSERT INTO debts VALUES (?,?,?)",
                (debtor, creditor, amount - reverse[0])
            )

        else:

            cursor.execute(
                "DELETE FROM debts WHERE debtor=? AND creditor=?",
                (creditor, debtor)
            )

    else:

        cursor.execute(
            "SELECT amount FROM debts WHERE debtor=? AND creditor=?",
            (debtor, creditor)
        )

        row = cursor.fetchone()

        if row:

            cursor.execute(
                "UPDATE debts SET amount=? WHERE debtor=? AND creditor=?",
                (row[0] + amount, debtor, creditor)
            )

        else:

            cursor.execute(
                "INSERT INTO debts VALUES (?,?,?)",
                (debtor, creditor, amount)
            )

    conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("Мой баланс", callback_data="mybalance")],
        [InlineKeyboardButton("Общий баланс", callback_data="balance")],
        [InlineKeyboardButton("Очистить все долги", callback_data="reset")]
    ]

    await update.message.reply_text(
        "Меню",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user.username

    if query.data == "balance":

        cursor.execute("SELECT * FROM debts")
        rows = cursor.fetchall()

        if not rows:
            await query.message.reply_text("Долгов нет")
            return

        people = {}

        for d, c, a in rows:

            if d not in people:
                people[d] = {"owe": [], "owed": []}

            if c not in people:
                people[c] = {"owe": [], "owed": []}

            people[d]["owe"].append((c, a))
            people[c]["owed"].append((d, a))

        text = ""

        for p, data in people.items():

            text += f"\n{p}\n"

            total_owe = sum(x[1] for x in data["owe"])
            total_owed = sum(x[1] for x in data["owed"])

            for c, a in data["owe"]:
                text += f"должен {c}: {a:.2f}\n"

            text += f"итого должен: {total_owe:.2f}\n"

            for d, a in data["owed"]:
                text += f"должны {d}: {a:.2f}\n"

            text += f"итого должны: {total_owed:.2f}\n"

        await query.message.reply_text(text)


    if query.data == "mybalance":

        cursor.execute("SELECT * FROM debts")
        rows = cursor.fetchall()

        owe = []
        owed = []

        for d, c, a in rows:

            if d == user:
                owe.append((c, a))

            if c == user:
                owed.append((d, a))

        text = f"Баланс {user}\n\n"

        for c, a in owe:
            text += f"вы должны {c}: {a:.2f}\n"

        text += "\n"

        for d, a in owed:
            text += f"{d} должен вам: {a:.2f}\n"

        await query.message.reply_text(text)


    if query.data == "reset":

        cursor.execute("DELETE FROM debts")
        cursor.execute("DELETE FROM purchases")

        conn.commit()

        await query.message.reply_text("Все долги очищены")


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    payer = update.message.from_user.username

    amount = float(context.args[0])
    item = context.args[1]

    users = [u.replace("@", "") for u in context.args[2:]]

    include_self = True

    if users and users[0] == "noself":

        include_self = False
        users = users[1:]

    if include_self:
        users.append(payer)

    share = amount / len(users)

    for u in users:

        if u != payer:
            normalize(u, payer, share)

    cursor.execute(
        "INSERT INTO purchases (payer,item,amount,participants,share) VALUES (?,?,?,?,?)",
        (payer, item, amount, ",".join(users), share)
    )

    purchase_id = cursor.lastrowid

    conn.commit()

    await update.message.reply_text(
        f"Покупка добавлена\nID: {purchase_id}\n{item} — {amount}\nдоля: {share:.2f}"
    )


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):

    debtor = update.message.from_user.username
    creditor = context.args[0].replace("@", "")
    amount = float(context.args[1])

    normalize(creditor, debtor, amount)

    await update.message.reply_text("Платеж учтен")


async def delete_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):

    pid = int(context.args[0])

    cursor.execute(
        "SELECT payer,participants,share FROM purchases WHERE id=?",
        (pid,)
    )

    row = cursor.fetchone()

    if not row:

        await update.message.reply_text("Покупка не найдена")
        return

    payer, participants, share = row

    users = participants.split(",")

    for u in users:

        if u != payer:
            normalize(payer, u, share)

    cursor.execute(
        "DELETE FROM purchases WHERE id=?",
        (pid,)
    )

    conn.commit()

    await update.message.reply_text("Покупка удалена")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("delete", delete_purchase))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
