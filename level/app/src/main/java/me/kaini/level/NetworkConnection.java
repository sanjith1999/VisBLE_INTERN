package me.kaini.level;

import java.util.Objects;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class NetworkConnection {
    private OkHttpClient client=null;
    private String results;
    public static final MediaType JSON =
            MediaType.parse("application/json; charset=utf-8");
    public NetworkConnection(){
        client=new OkHttpClient();
    }
    private static final String BASE_URL ="http://10.19.90.242:5000/";

    public String sendhori(int yaw, int roll,int pitch){
        final String methodPath = "send/" + String.valueOf(yaw)+"/"+String.valueOf(roll)+"/"+String.valueOf(pitch);
        Request.Builder builder = new Request.Builder();
        builder.url(BASE_URL + methodPath);
        Request request = builder.build();
        try {
            Response response = client.newCall(request).execute();
            results=response.body().string();
        }catch (Exception e){
            e.printStackTrace();
        }
        return results;
    }
    public String calculate(){
        final String methodPath = "calculate/";
        Request.Builder builder = new Request.Builder();
        builder.url(BASE_URL + methodPath);
        Request request = builder.build();
        try {
            Response response = client.newCall(request).execute();
            results= Objects.requireNonNull(response.body()).string();
        }catch (Exception e){
            e.printStackTrace();
        }
        return results;
    }
}
