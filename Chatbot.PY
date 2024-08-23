import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler
import openai
import json
from difflib import get_close_matches as yakin_sonuclari_getir

# OpenAI API key
openai.api_key = ''

# Telegram bot API key
TELEGRAM_API_KEY = ''

# Veritabanı dosyasının yolu
VERITABANI_DOSYASI = 'eticaret.json'

# Logging yapılandırması
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Veritabanını yükleyen fonksiyon
def vt_yukle():
    try:
        with open(VERITABANI_DOSYASI, 'r', encoding='utf-8') as dosya:
            return json.load(dosya)
    except FileNotFoundError:
        return {"urunler": [], "sohbetler": []}

# Veritabanını yazan fonksiyon
def vt_yaz(veriler):
    with open(VERITABANI_DOSYASI, 'w', encoding='utf-8') as dosya:
        json.dump(veriler, dosya, indent=2, ensure_ascii=False)

# /start komutu için işleyici
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info(f"User {user.username} started the bot.")
    await update.message.reply_text('Hello! How can I help you?')

# Mesajları işleyen fonksiyon
async def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    message_text = update.message.text
    logger.info(f"Received message from {user.username}: {message_text}")

    veritabani = vt_yukle()
    soru = update.message.text.lower()

    urun_isimleri = [urun["isim"] for urun in veritabani["urunler"]]
    markalar = list(set([urun["marka"].lower() for urun in veritabani["urunler"]]))
    kategoriler = list(set([urun["kategori"].lower() for urun in veritabani["urunler"]]))
    sohbet_sorulari = [sohbet["soru"].lower() for sohbet in veritabani["sohbetler"]]

    # Sohbet sorularını kontrol et
    sohbet_sonuclari = yakin_sonuclari_getir(soru, sohbet_sorulari, n=1, cutoff=0.8)
    if sohbet_sonuclari:
        cevap = next(sohbet for sohbet in veritabani["sohbetler"] if sohbet["soru"].lower() == sohbet_sonuclari[0])["cevap"]
        await update.message.reply_text(cevap)
        return

    # Kullanıcının sorusu ile markaları ve kategorileri karşılaştır
    gelen_sonuc = yakin_sonuclari_getir(soru, urun_isimleri, n=5, cutoff=0.4)
    markaya_uygun = yakin_sonuclari_getir(soru, markalar, n=5, cutoff=0.4)
    kategoriye_uygun = yakin_sonuclari_getir(soru, kategoriler, n=5, cutoff=0.4)

    if gelen_sonuc:
        if len(gelen_sonuc) == 1:
            verilecek_cevap = next(urun for urun in veritabani["urunler"] if urun["isim"] == gelen_sonuc[0])
            await update.message.reply_text(
                f"Ürün: {verilecek_cevap['isim']}\nMarka: {verilecek_cevap['marka']}\nKategori: {verilecek_cevap['kategori']}\nAçıklama: {verilecek_cevap['aciklama']}\nLink: {verilecek_cevap['link']}\nFiyat: {verilecek_cevap['fiyat']}"
            )
        else:
            keyboard = [
                [InlineKeyboardButton(urun, callback_data=urun)]
                for urun in gelen_sonuc
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('Bunu mu demek istediniz?', reply_markup=reply_markup)
    elif markaya_uygun:
        markaya_uygun = markaya_uygun[0]
        uygun_urunler = [urun for urun in veritabani["urunler"] if urun["marka"].lower() == markaya_uygun]
        kategoriler = list(set([urun["kategori"] for urun in uygun_urunler]))

        keyboard = [
            [InlineKeyboardButton(kategori, callback_data=f"marka:{markaya_uygun}:{kategori}")]
            for kategori in kategoriler
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"{markaya_uygun} markasının kategorileri:", reply_markup=reply_markup)
    elif kategoriye_uygun:
        kategoriye_uygun = kategoriye_uygun[0]
        uygun_urunler = [urun for urun in veritabani["urunler"] if urun["kategori"].lower() == kategoriye_uygun]

        keyboard = [
            [InlineKeyboardButton(urun["isim"], callback_data=urun["isim"])]
            for urun in uygun_urunler
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"{kategoriye_uygun} kategorisindeki ürünler:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Üzgünüm, aradığınız ürünü veya bilgiyi bulamadım.")

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user = query.from_user
    logger.info(f"Button clicked by {user.username}: {query.data}")

    if "marka:" in query.data:
        _, marka, kategori = query.data.split(":")
        veritabani = vt_yukle()
        uygun_urunler = [urun for urun in veritabani["urunler"] if urun["marka"].lower() == marka and urun["kategori"] == kategori]

        keyboard = [
            [InlineKeyboardButton(urun["isim"], callback_data=urun["isim"])]
            for urun in uygun_urunler
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"{marka} markasının {kategori} kategorisindeki ürünler:", reply_markup=reply_markup)
    else:
        veritabani = vt_yukle()
        urun = next(urun for urun in veritabani["urunler"] if urun["isim"] == query.data)
    
        await query.edit_message_text(
            text=f"Ürün: {urun['isim']}\nMarka: {urun['marka']}\nKategori: {urun['kategori']}\nAçıklama: {urun['aciklama']}\nLink: {urun['link']}\nFiyat: {urun['fiyat']}"
        )

# /newdata komutu için işleyiciler
URUN_ISMI, URUN_MARKASI, URUN_KATEGORISI, URUN_ACIKLAMASI, URUN_LINKI, URUN_FIYATI = range(6)

async def newdata(update: Update, context: CallbackContext):
    await update.message.reply_text("Ürünün ismi nedir?")
    return URUN_ISMI

async def urun_ismi(update: Update, context: CallbackContext):
    context.user_data['urun_ismi'] = update.message.text
    await update.message.reply_text("Ürünün markası nedir?")
    return URUN_MARKASI

async def urun_markasi(update: Update, context: CallbackContext):
    context.user_data['urun_markasi'] = update.message.text
    await update.message.reply_text("Ürünün kategorisi nedir?")
    return URUN_KATEGORISI

async def urun_kategorisi(update: Update, context: CallbackContext):
    context.user_data['urun_kategorisi'] = update.message.text
    await update.message.reply_text("Ürünün açıklaması nedir?")
    return URUN_ACIKLAMASI

async def urun_aciklamasi(update: Update, context: CallbackContext):
    context.user_data['urun_aciklamasi'] = update.message.text
    await update.message.reply_text("Ürünün linki nedir?")
    return URUN_LINKI

async def urun_linki(update: Update, context: CallbackContext):
    context.user_data['urun_linki'] = update.message.text
    await update.message.reply_text("Ürünün fiyatı nedir?")
    return URUN_FIYATI

async def urun_fiyati(update: Update, context: CallbackContext):
    urun_ismi = context.user_data['urun_ismi']
    urun_markasi = context.user_data['urun_markasi']
    urun_kategorisi = context.user_data['urun_kategorisi']
    urun_aciklamasi = context.user_data['urun_aciklamasi']
    urun_linki = context.user_data['urun_linki']
    urun_fiyati = update.message.text

    yeni_urun = {
        "isim": urun_ismi,
        "marka": urun_markasi,
        "kategori": urun_kategorisi,
        "aciklama": urun_aciklamasi,
        "link": urun_linki,
        "fiyat": urun_fiyati
    }

    veritabani = vt_yukle()
    veritabani["urunler"].append(yeni_urun)
    vt_yaz(veritabani)

    await update.message.reply_text("Yeni ürün başarıyla eklendi!")
    return ConversationHandler.END

async def iptal(update: Update, context: CallbackContext):
    await update.message.reply_text("İşlem iptal edildi.")
    return ConversationHandler.END

# /datalist komutu için işleyici
async def datalist(update: Update, context: CallbackContext):
    await update.message.reply_document(document=open(VERITABANI_DOSYASI, 'rb'))

# /edit komutu için işleyici
async def edit(update: Update, context: CallbackContext):
    urun_ismi = ' '.join(context.args)
    veritabani = vt_yukle()
    for urun in veritabani["urunler"]:
        if urun["isim"] == urun_ismi:
            context.user_data['edit_urun'] = urun
            await update.message.reply_text(f"Mevcut bilgiler:\nIsim: {urun['isim']}\nMarka: {urun['marka']}\nKategori: {urun['kategori']}\nAçıklama: {urun['aciklama']}\nLink: {urun['link']}\nFiyat: {urun['fiyat']}\n\nYeni ismi girin (değiştirmeyecekseniz mevcut bilgiyi tekrar girin):")
            return URUN_ISMI
    await update.message.reply_text(f"{urun_ismi} isminde bir ürün bulunamadı.")
    return ConversationHandler.END

# /delete komutu için işleyici
async def delete(update: Update, context: CallbackContext):
    urun_ismi = ' '.join(context.args)
    veritabani = vt_yukle()
    yeni_urunler = [urun for urun in veritabani["urunler"] if urun["isim"] != urun_ismi]
    if len(yeni_urunler) == len(veritabani["urunler"]):
        await update.message.reply_text(f"{urun_ismi} isminde bir ürün bulunamadı.")
    else:
        veritabani["urunler"] = yeni_urunler
        vt_yaz(veritabani)
        await update.message.reply_text(f"{urun_ismi} ürünü başarıyla deleteindi.")

# Yeni sohbet ekleme işlemi için durumlar
SOHBET_SORU, SOHBET_CEVAP = range(2)

# /newchat komutu için işleyici
async def newchat(update: Update, context: CallbackContext):
    await update.message.reply_text("Soru nedir?")
    return SOHBET_SORU

async def sohbet_soru(update: Update, context: CallbackContext):
    context.user_data['sohbet_soru'] = update.message.text
    await update.message.reply_text("Cevap nedir?")
    return SOHBET_CEVAP

async def sohbet_cevap(update: Update, context: CallbackContext):
    sohbet_soru = context.user_data['sohbet_soru']
    sohbet_cevap = update.message.text

    yeni_sohbet = {
        "soru": sohbet_soru,
        "cevap": sohbet_cevap
    }

    veritabani = vt_yukle()
    veritabani["sohbetler"].append(yeni_sohbet)
    vt_yaz(veritabani)

    await update.message.reply_text("Yeni sohbet başarıyla eklendi!")
    return ConversationHandler.END

# Main fonksiyonu
def main():
    application = Application.builder().token(TELEGRAM_API_KEY).build()

    conv_handler_newdata = ConversationHandler(
        entry_points=[CommandHandler('newdata', newdata)],
        states={
            URUN_ISMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_ismi)],
            URUN_MARKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_markasi)],
            URUN_KATEGORISI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_kategorisi)],
            URUN_ACIKLAMASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_aciklamasi)],
            URUN_LINKI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_linki)],
            URUN_FIYATI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_fiyati)],
        },
        fallbacks=[CommandHandler('iptal', iptal)]
    )

    conv_handler_edit = ConversationHandler(
        entry_points=[CommandHandler('edit', edit)],
        states={
            URUN_ISMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_ismi)],
            URUN_MARKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_markasi)],
            URUN_KATEGORISI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_kategorisi)],
            URUN_ACIKLAMASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_aciklamasi)],
            URUN_LINKI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_linki)],
            URUN_FIYATI: [MessageHandler(filters.TEXT & ~filters.COMMAND, urun_fiyati)],
        },
        fallbacks=[CommandHandler('iptal', iptal)]
    )

    conv_handler_newchat = ConversationHandler(
        entry_points=[CommandHandler('newchat', newchat)],
        states={
            SOHBET_SORU: [MessageHandler(filters.TEXT & ~filters.COMMAND, sohbet_soru)],
            SOHBET_CEVAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, sohbet_cevap)],
        },
        fallbacks=[CommandHandler('iptal', iptal)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("datalist", datalist))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(conv_handler_newdata)
    application.add_handler(conv_handler_edit)
    application.add_handler(conv_handler_newchat)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
        