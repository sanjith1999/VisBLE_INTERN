package me.kaini.level;

import android.content.Context;
import android.content.res.TypedArray;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PointF;
import android.os.Vibrator;
import android.util.AttributeSet;
import android.view.View;

/**
 * LEVEL CONTROL
 * BY SETTING{@link #setAngle(double, double)}
 * @author LI
 */
public class LevelView extends View {

    //CIRCLE RADIUS
    private float mLimitRadius = 0;

    //BUBBLE RADIUS
    private float mBubbleRadius;

    // MAXIMUM LIMIT CIRCLE COLOR
    private int mLimitColor;

    // LIMIT RING WIDTH
    private float mLimitCircleWidth;

    //BUBBLE CENTER STANDARD CIRCLE COLOR
    private int mBubbleRuleColor;

    //BUBBLE CENTER STANDARD CIRCLE WIDTH
    private float mBubbleRuleWidth;

    //BUBBLE CENTER STANDARD CIRCLE RADIUS
    private float mBubbleRuleRadius;

    //COLOR AFTER LEVEL
    private int mHorizontalColor;

    // BUBBLE COLOR
    private int mBubbleColor;

    private Paint mBubblePaint;
    private Paint mLimitPaint;
    private Paint mBubbleRulePaint;

    // CENTER POINT CO-ORDINATES
    private PointF centerPnt = new PointF();
    private PointF centerPnt2 = new PointF();

    // CALCULATED BUBBLE POINT
    private PointF bubblePoint;
    private PointF bubblePoint2;
    private double pitchAngle = -90;
    private double rollAngle = -90;
    private double azimuthAngle = -90;
    private Vibrator vibrator;

    public LevelView(Context context) {
        super(context);
        init(null, 0);
    }

    public LevelView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init(attrs, 0);
    }

    public LevelView(Context context, AttributeSet attrs, int defStyle) {
        super(context, attrs, defStyle);
        init(attrs, defStyle);
    }

    private void init(AttributeSet attrs, int defStyle) {
        // Load attributes
        final TypedArray a = getContext().obtainStyledAttributes(
                attrs, R.styleable.LevelView, defStyle, 0);

        mBubbleRuleColor = a.getColor(R.styleable.LevelView_bubbleRuleColor, mBubbleRuleColor);

        mBubbleColor = a.getColor(R.styleable.LevelView_bubbleColor, mBubbleColor);
        mLimitColor = a.getColor(R.styleable.LevelView_limitColor, mLimitColor);

        mHorizontalColor = a.getColor(R.styleable.LevelView_horizontalColor, mHorizontalColor);


        mLimitRadius = (float) (.8 * a.getDimension(R.styleable.LevelView_limitRadius, mLimitRadius));
        mBubbleRadius = a.getDimension(R.styleable.LevelView_bubbleRadius, mBubbleRadius);
        mLimitCircleWidth = a.getDimension(R.styleable.LevelView_limitCircleWidth, mLimitCircleWidth);

        mBubbleRuleWidth = a.getDimension(R.styleable.LevelView_bubbleRuleWidth, mBubbleRuleWidth);

        mBubbleRuleRadius = a.getDimension(R.styleable.LevelView_bubbleRuleRadius, mBubbleRuleRadius);


        a.recycle();


        mBubblePaint = new Paint();

        mBubblePaint.setColor(mBubbleColor);
        mBubblePaint.setStyle(Paint.Style.FILL);
        mBubblePaint.setAntiAlias(true);

        mLimitPaint = new Paint();

        mLimitPaint.setStyle(Paint.Style.STROKE);
        mLimitPaint.setColor(mLimitColor);
        mLimitPaint.setStrokeWidth(mLimitCircleWidth);
        //抗锯齿
        mLimitPaint.setAntiAlias(true);

        mBubbleRulePaint = new Paint();
        mBubbleRulePaint.setColor(mBubbleRuleColor);
        mBubbleRulePaint.setStyle(Paint.Style.STROKE);
        mBubbleRulePaint.setStrokeWidth(mBubbleRuleWidth);
        mBubbleRulePaint.setAntiAlias(true);

        vibrator = (Vibrator) getContext().getSystemService(Context.VIBRATOR_SERVICE);

    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        super.onMeasure(widthMeasureSpec, heightMeasureSpec);

        calculateCenter(widthMeasureSpec, heightMeasureSpec);
    }

    private void calculateCenter(int widthMeasureSpec, int heightMeasureSpec) {
        int width = MeasureSpec.makeMeasureSpec(widthMeasureSpec, MeasureSpec.UNSPECIFIED);

        int height = MeasureSpec.makeMeasureSpec(heightMeasureSpec, MeasureSpec.UNSPECIFIED);

        int center = Math.min(width, height) / 2;

        centerPnt.set(width/2,height/4);
        centerPnt2.set(width/2,3*height/4);
    }


    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        boolean isCenter = isCenter(bubblePoint,centerPnt) || isCenter(bubblePoint2,centerPnt2);
        int limitCircleColor = isCenter ? mHorizontalColor : mLimitColor;
        int bubbleColor = isCenter ? mHorizontalColor : mBubbleColor;

        //VIBRATE WHEN LEVEL
        if(isCenter){
            vibrator.vibrate(10);
        }

        mBubblePaint.setColor(bubbleColor);
        mLimitPaint.setColor(limitCircleColor);

        canvas.drawCircle(centerPnt.x, centerPnt.y, mBubbleRuleRadius, mBubbleRulePaint);
        canvas.drawCircle(centerPnt2.x, centerPnt2.y, mBubbleRuleRadius, mBubbleRulePaint);
        canvas.drawCircle(centerPnt.x, centerPnt.y, mLimitRadius, mLimitPaint);
        canvas.drawCircle(centerPnt2.x, centerPnt2.y, mLimitRadius, mLimitPaint);

        drawBubble(canvas);

    }

    private boolean isCenter(PointF bubblePoint, PointF centerPoint){

        if(bubblePoint == null){
            return false;
        }

        return Math.abs(bubblePoint.x - centerPoint.x) < 1 && Math.abs(bubblePoint.y - centerPoint.y) < 1;
    }

    private void drawBubble(Canvas canvas) {
        if(bubblePoint != null){
            canvas.drawCircle(bubblePoint.x, bubblePoint.y, mBubbleRadius, mBubblePaint);
            canvas.drawCircle(bubblePoint2.x,bubblePoint2.y, mBubbleRadius, mBubblePaint);
        }
    }

    /**
     * Convert angle to screen coordinate point.
     * @param rollAngle  RADIAN
     * @param pitchAngle RADIAN
     * @return
     */
    private PointF convertCoordinate(double rollAngle, double pitchAngle,PointF centerPoint, double radius){
        double scale = radius / Math.toRadians(90);

        // TAKE CENTER OF THE CIRCLE AS ORIGIN AND USE RADIANS TO EXPRESS CO-ORDINATES
        double x0 = -(rollAngle * scale);
        double y0 = -(pitchAngle * scale);

        // USE SCREEN CO-ORDINATES TO REPRESENT BUBBLE POINTS
        double x = centerPoint.x - x0;
        double y = centerPoint.y - y0;

        return new PointF((float)x, (float)y);
    }

    /**
     *
     * @param pitchAngle (RADIAN)
     * @param rollAngle (RADIAN)
     */
    public void setAngle(double rollAngle, double pitchAngle,double azimuthAngle) {

        this.pitchAngle = pitchAngle;
        this.rollAngle = rollAngle;
        this.azimuthAngle = azimuthAngle;

        //CONSIDERING THAT THE BOUNDARY OF THE BUBBLE DOES NOT EXCEED LIMIT CIRCLE
        float limitRadius = mLimitRadius - mBubbleRadius;

        bubblePoint = convertCoordinate(rollAngle, pitchAngle,centerPnt, mLimitRadius);
        bubblePoint2 = convertCoordinate(rollAngle,azimuthAngle,centerPnt2,mLimitRadius);
        outLimit(bubblePoint, centerPnt,limitRadius);
        outLimit(bubblePoint2,centerPnt2,limitRadius);

        //THE CO-ORDINATES EXCEED THE LARGEST CIRCLE, TAKE THE POINT ON THE NORMAL CIRCLE
        if(outLimit(bubblePoint,centerPnt, limitRadius)){
            onCirclePoint(bubblePoint, centerPnt,limitRadius);
        }
        if(outLimit(bubblePoint2,centerPnt2,limitRadius)){
            onCirclePoint(bubblePoint2,centerPnt2,limitRadius);
        }

        invalidate();
    }

    /**
     * VERIFY WHETHER BUBBLE POINT EXCEEDS THE LIMIT{@link #mLimitRadius}
     * @param bubblePnt
     * @return
     */
    private boolean outLimit(PointF bubblePnt,PointF centerPoint,float limitRadius){

        float cSqrt = (bubblePnt.x - centerPoint.x)*(bubblePnt.x - centerPoint.x)
                + (centerPoint.y - bubblePnt.y) * + (centerPoint.y - bubblePnt.y);


        if(cSqrt - limitRadius * limitRadius > 0){
            return true;
        }
        return false;
    }

    /**
     * CALCULATE THE CENTER OF THE CIRCLE TO bubblePnt INTERSECTING WITH CIRCLE
     *
     * @param bubblePnt
     * @param centerPoint
     * @param limitRadius
     * @return
     */
    private PointF onCirclePoint(PointF bubblePnt, PointF centerPoint, double limitRadius) {
        double azimuth = Math.atan2((bubblePnt.y - centerPoint.y), (bubblePnt.x - centerPoint.x));
        azimuth = azimuth < 0 ? 2 * Math.PI + azimuth : azimuth;

        // CENTER, RADIUS, ANGLE => FIND THE CO-ORDINATE ON THE CIRCLE
        double x1 = centerPoint.x + limitRadius * Math.cos(azimuth);
        double y1 = centerPoint.y + limitRadius * Math.sin(azimuth);

        bubblePnt.set((float) x1, (float) y1);

        return bubblePnt;
    }


    public double getPitchAngle(){
        return this.pitchAngle;
    }

    public double getRollAngle(){
        return this.rollAngle;
    }

    public double getAzimuthAngle() {
        return this.azimuthAngle;
    }


}

