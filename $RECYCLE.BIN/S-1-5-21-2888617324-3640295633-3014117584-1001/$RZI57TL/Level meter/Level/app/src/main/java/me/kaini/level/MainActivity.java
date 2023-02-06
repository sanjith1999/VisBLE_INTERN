package me.kaini.level;

import android.content.Intent;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.AsyncTask;
import android.os.Bundle;

import android.provider.MediaStore;
import android.support.v7.app.AppCompatActivity;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * @author LI
 */
public class MainActivity extends AppCompatActivity implements SensorEventListener {
    NetworkConnection networkConnection = null;

    private SensorManager sensorManager;
    private Sensor acc_sensor;
    private Sensor mag_sensor;

    private float[] accValues = new float[3];
    private float[] magValues = new float[3];
    // 旋转矩阵，用来保存磁场和加速度的数据
    private float r[] = new float[9];
    // 模拟方向传感器的数据（原始数据为弧度）
    private float values[] = new float[3];

    int rollAngle=20, pitchAngle=0;

    private LevelView levelView;
    private TextView tvHorz;
    private TextView tvVert;
    private Button send;
    private Button calculate;


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_startcamerae);
        networkConnection = new NetworkConnection();

        levelView = (LevelView) findViewById(R.id.gv_hv);

        tvVert = (TextView) findViewById(R.id.tvv_vertical);
        tvHorz = (TextView) findViewById(R.id.tvv_horz);
        send = (Button) findViewById(R.id.send);
        calculate = (Button) findViewById(R.id.calculate);


        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        send.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
               // String a = tvHorz.getText().toString();
                // = a.substring(0, a.length() - 1);

                new AsyncTask<Integer, Void, String>() {
                    @Override
                    protected String doInBackground(Integer... integers) {
                        networkConnection.sendhori(integers[0].intValue());
                        return "sucesss";
                    }
                    @Override
                    protected void onPostExecute(String states) {
                        Toast.makeText(getApplicationContext(), states, Toast.LENGTH_SHORT).show();
                    }
                }.execute(Integer.valueOf(rollAngle));
            }
        });

        calculate.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {

                new AsyncTask<Void, Void, String>() {
                    @Override
                    protected String doInBackground(Void... integers) {

                        return networkConnection.calculate();
                    }
                    @Override
                    protected void onPostExecute(String states) {
                        JSONObject jObject1 = null;
                        try {
                            jObject1 = new JSONObject(states);
                        } catch (JSONException e) {
                            e.printStackTrace();
                        }

                        try {
                            Toast.makeText(getApplicationContext(), String.valueOf(jObject1.getDouble("横坐标")) + String.valueOf(jObject1.getDouble("纵坐标")), Toast.LENGTH_SHORT).show();
                        } catch (JSONException e) {
                            e.printStackTrace();
                        }
                    }
                }.execute();

            }
        });

    }
    public void startCamera(View view){
        Intent intent=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        startActivity(intent);
    }

    @Override
    public void onResume() {
        super.onResume();

        acc_sensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        mag_sensor = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD);
        // 给传感器注册监听：
        sensorManager.registerListener(this, acc_sensor, SensorManager.SENSOR_DELAY_NORMAL);
        sensorManager.registerListener(this, mag_sensor, SensorManager.SENSOR_DELAY_NORMAL);
    }

    @Override
    protected void onPause() {
        // 取消方向传感器的监听
        sensorManager.unregisterListener(this);
        super.onPause();
    }

    @Override
    protected void onStop() {
        // 取消方向传感器的监听
        sensorManager.unregisterListener(this);
        super.onStop();
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        // 获取手机触发event的传感器的类型
        int sensorType = event.sensor.getType();
        switch (sensorType) {
            case Sensor.TYPE_ACCELEROMETER:
                accValues = event.values.clone();
                break;
            case Sensor.TYPE_MAGNETIC_FIELD:
                magValues = event.values.clone();
                break;

        }

        SensorManager.getRotationMatrix(r, null, accValues, magValues);
        SensorManager.getOrientation(r, values);

        // 获取　沿着Z轴转过的角度
        float azimuth = values[0];

        // 获取　沿着X轴倾斜时　与Y轴的夹角
        float pitchAngle = values[1];

        // 获取　沿着Y轴的滚动时　与X轴的角度
        //此处与官方文档描述不一致，所在加了符号（https://developer.android.google.cn/reference/android/hardware/SensorManager.html#getOrientation(float[], float[])）
        float rollAngle = -values[2];

        onAngleChanged(rollAngle, pitchAngle, azimuth);

    }

    /**
     * 角度变更后显示到界面
     *
     * @param rollAngle
     * @param pitchAngle
     * @param azimuth
     */
    private void onAngleChanged(float rollAngle, float pitchAngle, float azimuth) {

        //levelView.setAngle(rollAngle, pitchAngle);
        //int roll = (int) Math.toDegrees((rollAngle));
        /* Log.d("水平", String.valueOf(roll) + "°"); */

        //tvHorz.setText(String.valueOf((int) Math.toDegrees(rollAngle)) + "°");
        //tvVert.setText(String.valueOf((int) Math.toDegrees(pitchAngle)) + "°");

        this.rollAngle=(int) Math.toDegrees(rollAngle);
        this.pitchAngle=(int) Math.toDegrees(pitchAngle);

    }


}
