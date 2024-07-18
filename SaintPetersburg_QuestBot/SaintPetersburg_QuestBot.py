import telebot
import random
import yaml
import emoji
from telebot import types
from ultralytics import YOLO
from PIL import Image


# прогон фотки через нейронку
def neuro(image):
    model = YOLO('best.pt')
    object = image
    preds = model.predict(source=object, save=True)
    for pred in preds:
        objects = []
        boxes = pred.boxes.cpu().numpy()
        for p in zip(boxes.cls, boxes.conf, boxes.xyxyn):
            objects.append(
                {'type': pred.names[int(p[0])],
                 'conf': float(p[1]),
                 'box': list(p[2].astype(float))})
        if len(objects) == 0:
            return None
        else:
            return str(objects[0]['type'])


bot = telebot.TeleBot('6769163018:AAEulb1HUP388PiELh08WRsD_Wh8CEnSe20')

# чтение yaml-файла и создание списков с объектами
with open("final_version.yaml", "r", encoding="utf-8") as file:
    data = yaml.full_load(file)

user_game = {}
user_start_message = {}


# Запуск игры
@bot.message_handler(commands=['start'])
def start(message):
    global user_game
    global user_start_message
    if message.chat.id not in user_start_message:
        user_game[message.chat.id] = []
        user_start_message[message.chat.id] = message
    else:
        bot.send_message(
            message.chat.id,
            'Эй! Мы же уже играем. '
            'Если хочешь начать игру сначала - останови предыдущую из меню',
        )
        return

    bot.clear_step_handler(message)
    bot.send_message(
        message.chat.id,
        'Привет! Я бот для квеста по Санкт-Петербургу. Правила крайне просты:'
        ' мы с тобой строим маршрут по достопремичательностям города, потом я '
        'тебе даю загадку и по ней тебе нужно отгадать, что же за объект я имел '
        'ввиду, сфотографировать его и отослать мне, и я отвечу тебе, прав ты или нет.',
    )
    start_game(message)


# Завершение игры
@bot.message_handler(commands=['stop'])
def stop(message):
    global user_game
    global user_start_message

    bot.send_message(
        message.chat.id,
        emoji.emojize('Окей, тогда возвращайся, как станет скучно :waving_hand:')
    )
    user_start_message.pop(message.chat.id)
    user_game.pop(message.chat.id)
    bot.clear_step_handler(message)


# Отдаем выбор района для игры
def start_game(message):
    global user_game
    global user_start_message

    bot.clear_step_handler(message)
    keyboard = types.InlineKeyboardMarkup()
    key_cen = (types.InlineKeyboardButton
               ('Центральный', callback_data='Cent'))
    key_push = (types.InlineKeyboardButton
                ('Пушкин', callback_data='Push'))
    key_ad = (types.InlineKeyboardButton
              ('Адмиралтейский', callback_data='Admir'))
    key_pet = (types.InlineKeyboardButton
               ('Петроградский', callback_data='Petro'))
    key_vas = (types.InlineKeyboardButton
               ('Василеостровский', callback_data='Vasil'))

    keyboard.add(key_ad, key_vas, key_pet, key_cen, key_push)
    bot.send_message(
        message.chat.id,
        'Итак, давай выберем район:',
        reply_markup=keyboard
    )


# Отправка загадки и подсказок
@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    global user_game
    global user_start_message

    bot.delete_message(
        callback.message.chat.id,
        callback.message.message_id
    )

    if callback.data == 'yes':
        start_game(user_start_message[callback.message.chat.id])
        return
    elif callback.data == 'no':
        stop(user_start_message[callback.message.chat.id])
        return

    districts = {
        'Cent': data['central_district'],
        'Push': data['Pushkin'],
        'Petro': data['Petrogradskiy_district'],
        'Vasil': data['Vasileostrovskiy_district'],
        'Admir': data['Admiralteyskiy_district']
    }

    new_location = (set(districts[callback.data])
                    .difference(set(user_game[callback.message.chat.id])))

    if len(new_location) == 0:
        bot.send_message(
            callback.chat.id,
            'В этом районе нет новых доступных объектов для игры :('
            )
        start_game(user_start_message[callback.message.chat.id])
        return

    user_game[callback.message.chat.id].append(
        random.choice(list(new_location))
    )

    game = user_game[callback.message.chat.id]
    bot.send_message(callback.message.chat.id, f'Отлично, тогда начнем!')
    ques = data[callback.data][game[-1]]['question']
    f1 = data[callback.data][game[-1]]['fact1']
    f2 = data[callback.data][game[-1]]['fact2']
    f3 = data[callback.data][game[-1]]['fact3']

    bot.send_message(
        callback.message.chat.id,
        f'Новая локация: \n\n {ques}',
        parse_mode='html'
    )
    bot.send_message(
        callback.message.chat.id, emoji.emojize(
        ':keycap_1: Первая подсказка: ' + f'\n\n <tg-spoiler>{f1}</tg-spoiler>'),
        parse_mode='html'
    )
    bot.send_message(
        callback.message.chat.id, emoji.emojize(
        ':keycap_2: Вторая подсказка: ' + f'\n\n <tg-spoiler>{f2}</tg-spoiler>'),
        parse_mode='html')
    bot.send_message(
        callback.message.chat.id, emoji.emojize(
        ':keycap_3: Третья подсказка: ' + f'\n\n <tg-spoiler>{f3}</tg-spoiler>'),
        parse_mode='html'
    )


# Обработка  фотографии пользователя и проверка ее на соответствие ответа
@bot.message_handler(content_types=['photo'])
def photo(message):
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open("image.jpg", 'wb') as new_file:
        new_file.write(downloaded_file)
    with Image.open("image.jpg") as img:
        img.load()
    result = neuro(img)
    global user_game

    if result is None:
        bot.send_message(
            message.chat.id,
            'Объект не удалось распознать. Сфотографируй еще раз. '
            'Попробуй это сделать так, чтобы он на фото был виден целиком.'
        )

    elif result in user_game[message.chat.id]:
        keyboard = types.InlineKeyboardMarkup()
        key_yes = types.InlineKeyboardButton('Давай', callback_data='yes')
        key_no = types.InlineKeyboardButton('Хватит', callback_data='no')
        keyboard.add(key_yes, key_no)

        bot.send_message(
            message.chat.id,
            'Класс, все верно, хочешь отгадать еще один объект?',
            reply_markup=keyboard
        )

        bot.register_next_step_handler(message, callback_message)
    else:
        bot.send_message(
            message.chat.id,
            'Неправильно... Если ты уверен, что правильно определил объект,'
            ' то сфотографируй его повторно, старайся сделать так, чтобы на '
            'фото был виден весь объект, а не его часть. ')


bot.infinity_polling()
