from flask import Flask, jsonify
from werkzeug.routing import IntegerConverter
import rtls_example_with_rtls_util
import numpy as np
import matplotlib.pyplot as plt
import time
from _csv import Dialect as _Dialect
import csv
#处理负数值
class SignedIntConverter(IntegerConverter):
    regex = r'-?\d+'
app = Flask(__name__)
app.url_map.converters['signed_int'] = SignedIntConverter
#存储输入值：AOA和水平角

aoabefore = [1]
aoa= [[] for i in range(1)]
lev = []

#路由设置
@app.route('/send/<signed_int:horiz>', methods=['GET'])
def get_angle(horiz):
    lev.append(horiz)
    print("平面角" + str(horiz))
    aoabefore.clear()
    aoabefore.extend(aoa.copy())

    aoa.clear()
    aoa.extend(rtls_example_with_rtls_util.main())
    return jsonify({'state': 'success'})

@app.route('/calculate/', methods=['GET'])
def calculate():

    print("转动前："+str(aoabefore)+'\n'+"转动后： " + str(aoa) +'\n'+"转动角： "+ str(lev))
    #aoa_image()
    u = []
    v = []
    minnumber = min(len(aoabefore), len(aoa))

    for i in range(minnumber):
        for j in range(minnumber):
            (temp1, temp2) = (rtls_example_with_rtls_util.calculate(lev[-2] - lev[-1], aoabefore[i], aoa[j]))

            if (temp1 != 1):
                u.append(temp1)
                v.append(temp2)

    return jsonify({'state': 'success'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
