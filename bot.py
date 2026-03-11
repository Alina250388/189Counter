import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8755685024:AAHbEJZqUOMDwkCsJ3BGybcJ2_766WbtdMQ"

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS debts (
debtor TEXT,
creditor TEXT,
amount REAL
)
""")

conn.commit()


def add_debt(debtor, creditor, amount):

    cursor.execute(
    "SELECT amount FROM debts WHERE debtor=? AND creditor=?",
    (debtor, creditor)
    )

    row = cursor.fetchone()

    if row:
        new_amount = row[0] + amount
        cursor.execute(
        "UPDATE debts SET amount=? WHERE debtor=? AND creditor=?",
        (new_amount, debtor, creditor)
        )
    else:
        cursor.execute(
        "INSERT INTO debts VALUES (?,?,?)",
        (debtor, creditor, amount)
        )

    conn.commit()


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    payer = update.message.from_user.username
    amount = float(context.args[0])
    item = context.args[1]

    users = [u.replace("@","") for u in context.args[2:]]

    users.append(payer)

    share = amount / len(users)

    for u in users:
        if u != payer:
            add_debt(u, payer, share)

    await update.message.reply_text(
    f"{payer} купил {item}. Каждый должен {share:.2f}"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT * FROM debts WHERE amount > 0")
    rows = cursor.fetchall()

    text = ""

    for d,c,a in rows:
        text += f"{d} → {c}: {a:.2f}\n"

    if text == "":
        text = "Долгов нет"

    await update.message.reply_text(text)


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):

    debtor = update.message.from_user.username
    creditor = context.args[0].replace("@","")
    amount = float(context.args[1])

    add_debt(debtor, creditor, -amount)

    await update.message.reply_text("Оплата записана")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("pay", pay))

app.run_polling()
