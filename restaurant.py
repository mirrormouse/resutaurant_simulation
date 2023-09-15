import redis
import pickle
import time
# Redis に接続します
r = redis.Redis(host='localhost', port=6379, db=0)



class Item: #商品
    def __init__(self, name, price, ingredients, time):
        self.name = name
        self.price = price
        self.ingeredients = ingredients
        self.time = time #調理時間

class Menu:
    def __init__(self, items):
        self.items = items
    def get_item(self, name):
        for item in self.items:
            if item.name == name:
                return item
        return None


class Clerk: #ホール担当
    def __init__(self, turntime, listentime, carrytime, name):
        self.turntime = turntime
        self.listentime = listentime #注文を聞くのにかかる時間
        self.carrytime = carrytime #料理を運ぶのにかかる時間
        self.name = name
    def run(self, start):
        while True:
            time.sleep(self.turntime)
            order_res = r.lpop('order')
            dish_res = r.lpop('dish')
            message_res = r.lpop('message')
            if order_res is not None: #注文がある場合
                order = order_res
                time.sleep(self.listentime)
                r.rpush('demand', order) #シェフに注文を伝える
            elif dish_res is not None: #料理ができた場合
                customer, item = pickle.loads(dish_res)
                time.sleep(self.carrytime)
                print(f"{round(time.time()-start,3)} From 店員{self.name}, To {customer}：{item.name}です。")
            elif message_res is not None: #メッセージがある場合
                customer, message = pickle.loads(message_res)
                time.sleep(self.carrytime)
                print(f"{round(time.time()-start,3)} From 店員{self.name}, To {customer}：{message}")
            

class Chief: #料理人
    def __init__(self, menu, turntime, checktime, ordertime, gettime, name):
        self.menu = menu
        self.turntime = turntime
        self.checktime = checktime # 在庫チェックにかかる時間
        self.ordertime = ordertime # 材料を注文するのにかかる時間
        self.gettime = gettime # 材料を調達するのにかかる時間
        self.name = name
    def run(self, start):
        while True:
            time.sleep(self.turntime)
            demand_res = r.lpop('demand')
            ingredient_res = r.lpop('source')
            if demand_res is not None:
                order = pickle.loads(demand_res) #注文を確認
                item = self.menu.get_item(order[0]) #注文された商品を確認
                customer = order[1]
                stock_ok = True
                for ingredient, amount in item.ingeredients.items():
                    remain = r.hget('stock', ingredient) #在庫を確認
                    if int(remain) < amount * 2:
                        if r.hget('info', ingredient) is None:
                            print(f"{round(time.time()-start,3)} シェフ{self.name}：{ingredient}の残数{remain.decode()}を確認、{ingredient}を注文")
                            time.sleep(self.ordertime)
                            r.rpush('ingredient_order', ingredient) #在庫を注文
                            r.hset('info', ingredient, "ordered") #注文済みの材料を記録
                    if int(remain) < amount:
                        stock_ok = False
                time.sleep(self.checktime)
                if stock_ok: #在庫がある場合
                    for ingredient, amount in item.ingeredients.items():
                        r.hincrby('stock', ingredient, -amount) #在庫を減らす
                    time.sleep(item.time)
                    print(f"{round(time.time()-start,3)} シェフ{self.name}：{item.name}完成")
                    r.rpush('dish', pickle.dumps((customer, item))) 
                else:
                    r.rpush('message', pickle.dumps((customer, '申し訳ありませんが材料を切らしています'))) #在庫がない場合
                    #print(f"{round(time.time()-start,3)} シェフ{self.name}：品切れのため{customer}氏の{item.name}が作れなかったことを報告")
            if ingredient_res is not None:
                ingredient, amount = pickle.loads(ingredient_res)
                r.hincrby('stock', ingredient, amount) #在庫を増やす
                time.sleep(self.gettime)
                r.hdel('info', ingredient) #注文済みの材料を削除



class Source: #材料の調達元
    def __init__(self, ingredient, amount, time, turntime):
        self.ingredient = ingredient 
        self.amount = amount #調達量
        self.time = time #調達時間
        self.turntime = turntime
    def run(self, start):
        while True:
            time.sleep(self.turntime)
            ingredient_order_res = r.lpop('ingredient_order')
            if ingredient_order_res is not None:
                ingredient = ingredient_order_res.decode()
                if ingredient == self.ingredient:
                    time.sleep(self.time)
                    print(f"{round(time.time()-start,3)} 調達元：{self.ingredient}を{self.amount}配達。")
                    r.rpush('source', pickle.dumps((ingredient, self.amount)))
                else:
                    r.rpush('ingredient_order', ingredient)
                    
if __name__ == '__main__':
    menu = Menu([
        Item('カレー', 900, {'野菜': 1, '米': 2}, 4),
        Item('ラーメン', 800, {'小麦粉': 2, '野菜': 2, '豚肉':2}, 3),
        Item('チャーハン', 850, {'米': 2, '卵': 1, '豚肉': 2}, 3),
        Item('豚汁', 600, {'豚肉': 1, '野菜': 1}, 0.5),
        Item('オムライス', 1000, {'米': 2, '卵': 2, '野菜': 1}, 3),
        Item('餃子', 800, {'小麦粉': 1, '豚肉': 1, '野菜': 1}, 2),
    ])
    r.flushall()
    r.hset('stock', '野菜', 10)
    r.hset('stock', '米', 15)
    r.hset('stock', '小麦粉', 5)
    r.hset('stock', '卵', 10)
    r.hset('stock', '豚肉', 8)
    sources = [
        Source('野菜', 50, 2, 0.01),
        Source('米', 50, 5, 0.02),
        Source('小麦粉', 50, 5, 0.01),
        Source('卵', 50, 4, 0.02),
        Source('豚肉', 50, 2, 0.01),
    ]
    chiefs = [
        Chief(menu, 0.01, 0.05, 0.05, 0.01, '佐藤'),
        Chief(menu, 0.02, 0.04, 0.12, 0.02, '鈴木'),
        Chief(menu, 0.03, 0.05, 0.1, 0.01, '高橋'),
    ]
    clerks = [
        Clerk(0.01, 0.3, 0.3, '渡辺'),
        Clerk(0.02, 0.3, 0.2, '伊藤'),
        Clerk(0.03, 0.3, 0.5, '田中'),
    ]
    # 店員、料理人、調達元を全てマルチプロセッシングで動作させる
    start_time = time.time()

    import multiprocessing
    for source in sources:
        multiprocessing.Process(target=source.run, args=(start_time,)).start()
    for chief in chiefs:
        multiprocessing.Process(target=chief.run, args=(start_time,)).start()
    for clerk in clerks:
        multiprocessing.Process(target=clerk.run, args=(start_time,)).start()
    # お客さんを作成
    import random
    customer_names = ['山田', '山口', '松本', '井上', '木村', '林', '斎藤', '清水', '山崎', '阿部',
                        '森', '池田', '橋本', '山下', '石川', '中島', '前田', '藤田', '小川', '後藤',
                        '岡田', '長谷川', '村上', '近藤', '石井', '坂本', '遠藤', '青木', '藤井', '西村'
                        , '福田', '太田', '三浦', '藤原', '岡本', '松田', '中野', '中川', '原田', '小野']
    
    
    print(f"{round(time.time()-start_time,3)} 開店しました")
    for i in range(10000):
        time.sleep((random.random() + random.random())* 2)
        item = random.choice(menu.items)
        name = random.choice(customer_names)
        print(f"{round(time.time()-start_time,3)} From {name}：注文お願いします、{item.name}をください。")
        r.rpush('order', pickle.dumps((item.name, name)))
        



