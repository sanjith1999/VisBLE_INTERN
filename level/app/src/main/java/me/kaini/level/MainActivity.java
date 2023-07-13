package me.kaini.level;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.AsyncTask;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

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
    // ROTATION MATRIX USED TO SAVE THE DATA OF MAGNETIC FIELD AND ACCELERATION
    private float r[] = new float[9];
    //DATA FROM THE SIMULATED ORIENTATION SENSOR(RAW DATA -> RADIANS)
    private float values[] = new float[3];


    int rollAngle = 20, pitchAngle = 0, azimuthAngle = 90;

    private LevelView levelView;
    private TextView tvHorz;
    private TextView tvVert;
    private TextView tvAxial;
    private Button send;
    private Button calculate;


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);
        networkConnection = new NetworkConnection();

        levelView = (LevelView) findViewById(R.id.gv_hv);

        tvVert = (TextView) findViewById(R.id.tvv_vertical);
        tvHorz = (TextView) findViewById(R.id.tvv_horz);
        tvAxial = (TextView) findViewById(R.id.tvv_axial);
        send = (Button) findViewById(R.id.send);
        calculate = (Button) findViewById(R.id.calculate);



        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        send.setOnClickListener(new View.OnClickListener() {
            @SuppressLint("StaticFieldLeak")
            @Override
            public void onClick(View v) {
                String a = tvHorz.getText().toString();
                // = a.substring(0, a.length() - 1);

                new AsyncTask<Integer, Void, String>() {
                    @Override
                    protected String doInBackground(Integer... integers) {
                        networkConnection.sendhori(integers[0].intValue(),integers[1].intValue(),integers[2].intValue());
                        return "sucesss";
                    }

                    @Override
                    protected void onPostExecute(String states) {
                        Toast.makeText(getApplicationContext(), states, Toast.LENGTH_SHORT).show();
                    }
                }.execute(Integer.valueOf(pitchAngle),Integer.valueOf(rollAngle),Integer.valueOf(azimuthAngle));
            }
        });

        calculate.setOnClickListener(new View.OnClickListener() {
            @SuppressLint("StaticFieldLeak")
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

    public void startCamera(View view) {
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        startActivity(intent);
    }

    @Override
    public void onResume() {
        super.onResume();

        acc_sensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        mag_sensor = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD);
        // REGISTER MONITORING FOR SENSORS：
        sensorManager.registerListener(this, acc_sensor, SensorManager.SENSOR_DELAY_NORMAL);
        sensorManager.registerListener(this, mag_sensor, SensorManager.SENSOR_DELAY_NORMAL);
    }

    @Override
    protected void onPause() {
        // CANCEL THE MONITORING OF THE DIRECT SENSOR
        sensorManager.unregisterListener(this);
        super.onPause();
    }

    @Override
    protected void onStop() {
        // CANCEL THE MONITORING OF THE DIRECT SENSOR
        sensorManager.unregisterListener(this);
        super.onStop();
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        // GET THE TYPE OF THE SENSOR THAT TRIGGERS THE EVENT ON THE PHONE
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

        // GET THE ANGLE ROTATED ALONG Z-AXIS
        float azimuthAngle = values[0];

        // GET THE ANGLE ROTATED ALONG X-AXIS
        float pitchAngle = values[1];

        // GET THE ANGLE ROTATED ALONG Y-AXIS
        // THIS IS INCONSISTENT WITH THE DESCRIPTION IN THE OFFICIAL DOCUMENT, WHERE SYMBOLS ARE ADDED（https://developer.android.google.cn/reference/android/hardware/SensorManager.html#getOrientation(float[], float[])）
        float rollAngle = -values[2];

        onAngleChanged(rollAngle, pitchAngle, azimuthAngle);

    }

    /**
     * AFTER THE ANGLE IS CHANGED IT WILL BE DISPLAYED ON THE INTERFACE
     *
     * @param rollAngle
     * @param pitchAngle
     * @param azimuthAngle
     */
    private void onAngleChanged(float rollAngle, float pitchAngle, float azimuthAngle) {

        levelView.setAngle(rollAngle, pitchAngle,azimuthAngle);
        int roll = (int) Math.toDegrees((rollAngle));
        /* Log.d("LEVEL", String.valueOf(roll) + "°"); */

        tvHorz.setText(String.valueOf((int) Math.toDegrees(rollAngle)) + "°");
        tvVert.setText(String.valueOf((int) Math.toDegrees(pitchAngle)) + "°");
        tvAxial.setText(String.valueOf((int) Math.toDegrees(azimuthAngle)) + "°");



        this.rollAngle = (int) Math.toDegrees(rollAngle);
        this.pitchAngle = (int) Math.toDegrees(pitchAngle);
        this.azimuthAngle = (int) Math.toDegrees(azimuthAngle);

    }


}
