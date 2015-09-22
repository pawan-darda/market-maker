from __future__ import absolute_import

import celery_config
import os, json
import redis
from celery import Celery

from flask import Flask, Blueprint, abort
from flask import jsonify, request, session
from flask import send_from_directory, render_template
from os import path, environ

app = Flask(__name__, template_folder='templates')
app.config.from_object(celery_config)

redis_server = redis.Redis('localhost',port=6379, db=1)

root_dir = os.path.dirname(os.getcwd())
static_dir = os.path.join(root_dir, 'dashboard','static')

def make_celery(app):
    c = Celery(app.import_name,
               broker=app.config['CELERY_BROKER_URL'],
               backend=app.config['CELERY_RESULTS_URL'])
    c.conf.update(app.config)
    TaskBase = c.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    c.Task = ContextTask
    return c

celery_app = make_celery(app)

@celery_app.task(name='tasks.add')
def add(x, y):
    return x + y

@celery_app.task(name='tasks.mul')
def mul(x, y):
    return x * y

@celery_app.task(name='tasks.sub')
def xsum(numbers):
    return sum(numbers)

@app.route("/test")
def test_celery(x=16, y=16):
    x = int(request.args.get("x", x))
    y = int(request.args.get("y", y))
    res = add.apply_async((x, y))
    context = {"id": res.task_id, "x": x, "y": y}
    result = "add((x){}, (y){})".format(context['x'], context['y'])
    goto = "{}".format(context['id'])
    return jsonify(result=result, goto=goto)

@app.route("/test/result/<task_id>")
def show_result(task_id):
    ret_val = add.AsyncResult(task_id).get(timeout=1.0)
    return repr(ret_val)

@app.route("/overall")
def overall():
    return render_template('dashboard.html')

@app.route("/developers")
def developers():
    return render_template('developers.html')

@app.route("/apps")
def apps():
    return render_template('dashboard_2.html')

@app.route("/apis")
def apis():
    return render_template('apis.html')

@app.route("/builds")
def build():

    list_data, tmpl_data = get_from_redis()
    return render_template('builds.html', data=tmpl_data , list=list_data)


@app.route("/build_data" , methods=['GET','POST'])
def build_data():
    if request.method == 'POST':
        #print request.data
        save_in_redis(request.data)
        return "Data received"
    else:
        list_data, tmpl_data = get_from_redis()
        return render_template('build_data.html', data=tmpl_data , list=list_data)

def save_in_redis(data):
    jdata = json.loads(data)
    build_name = jdata["build"]["buildName"]
    redis_server.sadd("TC:BUILD:NAMES", build_name )
    redis_server.rpush(build_name, data)

def get_from_redis():

    build_list = redis_server.smembers("TC:BUILD:NAMES")

    ret_data = {}
    list_data = []
    for build_name in build_list:
        list_data.append((build_name,))
        ret_data[build_name] = redis_server.lrange(build_name,0,4)

    return list_data, ret_data

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory(os.path.join(root_dir,'dashboard','static','js'), path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory(os.path.join(root_dir,'dashboard','static','css'), path)

@app.route('/fonts/<path:path>')
def send_fonts(path):
    return send_from_directory(os.path.join(root_dir,'dashboard','static','fonts'), path)

@app.route('/font-awesome/<path:path>')
def send_fa(path):
    return send_from_directory(os.path.join(root_dir,'dashboard','static','font-awesome'), path)

@app.route('/img/<path:path>')
def send_img(path):
    return send_from_directory( os.path.join(root_dir,'dashboard','static','img'), path)

if __name__ == "__main__":
    port = int(environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
