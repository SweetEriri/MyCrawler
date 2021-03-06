import requests, sqlite3
from lxml.html import fromstring
from requests.compat import urljoin
from sqlite3 import IntegrityError
from DESCipher import DESCipher


class Exam:
    url = 'http://www.somarx.cn/Chapter/ChapterList'
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/62.0.3202.75 Safari/537.36 '
    }
    chapter_range = {
        'mzdsxhzgteshzylltx': [],
        'marxism': [],
        'zgjdsgy': [],
        'sxddxyyfljc': []
    }
    course_id = {
        'mzdsxhzgteshzylltx': {'courseId': 3},
        'marxism': {'courseId': 1},
        'zgjdsgy': {'courseId': 2},
        'sxddxyyfljc': {'courseId': 4}
    }

    def __init__(self, password=None, dbname='exam_somarx.db'):
        self.cookies = requests.cookies.RequestsCookieJar()
        # 登陆后，获取session_id，保存id就能保持会话，不需要重复登陆了
        self.cookies.set('ASP.NET_SessionId', '', domain='www.somarx.cn', path='/')
        self.db = sqlite3.connect(dbname)
        self.cipher = DESCipher(password) if password else None
        for table in Exam.chapter_range:
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS "{}"(
                [_id] integer PRIMARY KEY AUTOINCREMENT
                ,[type] INTEGER
                ,[subject] VARCHAR(255) COLLATE NOCASE UNIQUE
                ,[a] VARCHAR(200) COLLATE NOCASE
                ,[b] VARCHAR(200) COLLATE NOCASE
                ,[c] VARCHAR(200) COLLATE NOCASE
                ,[d] VARCHAR(200) COLLATE NOCASE
                ,[e] VARCHAR(200) COLLATE NOCASE
                ,[answer] VARCHAR(200) COLLATE NOCASE
                ,[chapter] VARCHAR(200) COLLATE NOCASE
                );
            '''.format(table))

    def get_chapter_list(self):
        for course in Exam.course_id:
            if not Exam.chapter_range[course]:
                r = requests.get(Exam.url, params=Exam.course_id[course], cookies=self.cookies, headers=self.headers)
                html = fromstring(r.text)
                Exam.chapter_range[course] = [x.attrib['href'] for x in html.cssselect('.start-do')]

    def crawler(self):
        self.get_chapter_list()
        for course in Exam.chapter_range:
            for cid, chapter in enumerate(Exam.chapter_range[course]):
                r = requests.get(urljoin(self.url, chapter), cookies=self.cookies, headers=self.headers)
                html = fromstring(r.text)
                question = [q.text for q in html.cssselect('.question-word > p:nth-child(2)')]
                selection = html.cssselect('ol[type="A"]')
                right_ans = [a.text for a in html.cssselect('b.right-answer')]
                for ques, sel, ra in zip(question, selection, right_ans):
                    if self.cipher:
                        ques = self.cipher.encrypt(ques)

                    if ra in '对错':
                        ra = '1' if ra == '对' else '0'
                    data = {
                        'chapter': str(cid if course != 'mzdsxhzgteshzylltx' else cid + 1),
                        'question': ques,  # 题目
                        'answer': ra,
                        'a': str(),
                        'b': str(),
                        'c': str(),
                        'd': str(),
                        'e': str(),
                    }
                    # 1判断 2单选 3多选
                    data['type'] = 1 if data['answer'] in '01' else \
                        2 if len(data['answer']) == 1 else 3
                    try:
                        if data['type'] != 1:
                            for s, sc in zip(list('abcde'), sel.xpath('li/p/text()')):
                                data[s] = sc if not self.cipher else self.cipher.encrypt(sc)
                            self.db.execute("INSERT INTO {} (type, subject, a, b, c, d, e, answer, chapter) VALUES ("
                                            "?, ?, ?, ?, ?, ?, ?, ?, ?) ".format(course),
                                            (data['type'], data['question'],
                                             data['a'], data['b'], data['c'], data['d'], data['e'],
                                             data['answer'], data['chapter']))
                        else:
                            self.db.execute(
                                "INSERT INTO {} (type, subject, answer, chapter) VALUES (?, ?, ?, ?)".format(course),
                                (data['type'], data['question'], data['answer'], data['chapter']))
                    except IntegrityError:
                        pass
                print('{}第{}章已抓取'.format(course, data['chapter']), len(question), '条')
            print('{}已抓取'.format(course), len(self.db.execute('select * from {}'.format(course)).fetchall()), '条')
            self.db.commit()


if __name__ == '__main__':
    exam = Exam()
    exam.get_chapter_list()
    exam.crawler()
