import time
import serial
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
import math  #math lib

#oled setup
oled_serial = i2c(port=1, address=0x3D)
device = ssd1306(oled_serial)

#serial setup
ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
time.sleep(2)

#servo map
servo_positions = {
    "neutral":  (90, 75, 180, 0),
    "sad":      (90, 100, 180, 0),
    "happy":    (90, 70, 65, 115),
    "angry":    (90, 75, 90, 90),
    "confused": (90, 75, 135, 45),
}

#eye draw
def draw_expression(draw, expression, width=14, height=50):
    radius = 4
    top_margin = (64 - height) // 2
    left_center_x = 26 + 7
    right_center_x = 88 + 7

    def eye_shape(x, y, w, h):
        draw.pieslice((x, y, x + w, y + 2 * radius), 180, 360, fill=255)
        draw.pieslice((x, y + h - 2 * radius, x + w, y + h), 0, 180, fill=255)
        draw.rectangle((x, y + radius, x + w, y + h - radius), fill=255)

    if expression == "neutral":  #neutral eyes
        for cx in [left_center_x, right_center_x]:
            eye_shape(cx - width // 2, top_margin, width, height)

    elif expression == "happy":  #happy eyes
        eye_size = 14
        top = 20
        offset = 6
        for cx in [left_center_x, right_center_x]:
            draw.polygon([(cx - eye_size, top + eye_size), (cx, top), (cx + eye_size, top + eye_size)], fill=255)
            draw.polygon([(cx - eye_size + offset, top + eye_size), (cx, top + offset + 4), (cx + eye_size - offset, top + eye_size)], fill=0)

    elif expression == "sad":  #sad eyes
        eye_size = 14
        top = 34
        offset = 6
        for cx in [left_center_x, right_center_x]:
            draw.polygon([(cx - eye_size, top), (cx, top + eye_size), (cx + eye_size, top)], fill=255)
            draw.polygon([(cx - eye_size + offset, top), (cx, top + eye_size - offset - 4), (cx + eye_size - offset, top)], fill=0)

    elif expression == "confused":  #confused eyes
        for cx in [left_center_x, right_center_x]:
            for i in range(4):
                offset = i * 2
                draw.arc((cx - 6 + offset, 24 + offset, cx + 6 - offset, 36 - offset), 0, 360, fill=255)

    elif expression == "angry":  #angry eyes
        h = 30
        top = (64 - h) // 2
        for cx in [left_center_x, right_center_x]:
            x = cx - width // 2
            draw.rectangle((x, top, x + width, top + h), fill=255)
        draw.line((left_center_x - 8, 20, left_center_x + 8, 28), fill=255, width=2)
        draw.line((right_center_x - 8, 28, right_center_x + 8, 20), fill=255, width=2)

    else:  #fallback
        for cx in [left_center_x, right_center_x]:
            eye_shape(cx - width // 2, top_margin, width, height)

#transition
def animate_neutral_to(expression):
    for h in [50, 40, 30, 20, 10]:
        with canvas(device) as draw:
            draw_expression(draw, "neutral", height=h)
        time.sleep(0.04)
    with canvas(device) as draw:
        draw_expression(draw, expression)

#servo move
def move_servos(pan, tilt, left, right):
    cmd = f"{int(pan)},{int(tilt)},{int(left)},{int(right)}\n"
    ser.write(cmd.encode('utf-8'))
    print("Sent:", cmd.strip())

#set face
def set_expression(expression):
    animate_neutral_to(expression)
    if expression in servo_positions:
        move_servos(*servo_positions[expression])
    else:
        print("Unknown expression:", expression)

#dance loop
def dance_animation(update_rate=0.05):
    with canvas(device) as draw:
        draw_expression(draw)

    t = 0
    while stem_state == "playing":
        tilt = 80 + 5 * math.sin(t)
        left_wave = (math.sin(t) + 1) / 2
        left_arm = int(65 + left_wave * (180 - 65))
        right_wave = 1 - left_wave
        right_arm = int(0 + right_wave * (115 - 0))
        move_servos(90, int(tilt), left_arm, right_arm)
        time.sleep(update_rate)
        t += update_rate * 2

#main loop
if __name__ == "__main__":
    try:
        while True:
            choice = input("Enter expression (happy/sad/angry/confused/neutral/dance/q): ").strip()
            if choice == "q":
                break
            elif choice == "dance":
                dance_animation()
            else:
                set_expression(choice)
    finally:
        ser.close()
