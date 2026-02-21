import re
import os

# В ass_path использовать сырую строку(r'') или экранирование \.
ass_path = r'' # Сюда путь к файлу. Или относительный, если он находится в текущей директории или дочерних. Или полный.
# По умолчанию всё будет сохранено в директорию скрипта. Передайте path_to_write при инициализации объекта, если хотите сохранить куда-то ещё.
class Parser:
    def __init__(self, filename: str, path_to_write: str = ''):
        self.filename = os.path.abspath(filename)
        self.dummy = "1\n00:00:00,000 --> 00:00:00,000\n*Начало*\n\n"
        self.main_pattern = r'Dialogue: [^,]*,(?P<start>[^,]+),(?P<end>[^,]+),(?P<name>[^,]+)[,0]+(?P<phrase>.*)'
        self.ass = None
        self.base_filename = os.path.basename(self.filename).split('.')[0]
        self.result = {}
        self.path_to_write = path_to_write

    # Записывает текст из .ass файла в переменную self.ass
    def read_file(self):
        with open(self.filename, "r", encoding='utf-8') as file:
            self.ass = file.read()
        if self.ass:
            print("Файл прочитан.")

    # Парсит .ass файл в словарь в формате: "Имя" : [(1-ый тайминг, 2-ой тайминг, фраза), ...]
    def parse_ass(self):
        self.read_file()
        for match in re.finditer(self.main_pattern, self.ass):
            if match.group("name") not in self.result:
                self.result[match.group("name")] = []
            data_to_add = (match.group("start"), match.group("end"), match.group("phrase"))
            self.result[match.group("name")].append(data_to_add)

    # Записывает данные из словаря по разным .srt файлам
    def write_srt(self):
        for name, data in self.result.items():
            srt_name = self.path_to_write + f'{self.base_filename} {name}.srt'
            print(srt_name)

            with open(srt_name, "w", encoding="utf-8") as file:
                file.write(self.dummy)
                for i, (start, end, phrase) in enumerate(data, 2):
                    start_time = start.replace('.', ',') + "0"
                    end_time = end.replace('.', ',') + "0"

                    file.write(f'{i}\n{start_time} --> {end_time}\n{phrase}\n\n')

# Пример:
test = Parser(ass_path) # иниц объекта с указанием пути
test.parse_ass() # читает .ass файл и сохраняет распаршенный словарь
test.write_srt() # записывает все .srt файлы