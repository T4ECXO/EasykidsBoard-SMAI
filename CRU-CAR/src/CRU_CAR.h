#pragma once

// CRU-CAR is an add-on for the EasyKids 3in1 board package. EasyKids3in1.h
// supplies readline(), motor(), clamp(), and the line-sensor configuration.
#include <EasyKids3in1.h>

namespace cru_car {

// Header-only state: each sketch has one independent line-following controller.
static float previousError = 0;
static uint32_t lastUpdate = 0;
static bool hasPreviousError = false;

inline void calculateTrackLine2LR(int leftBaseSpeed, int rightBaseSpeed, float kp, float kd, int &left, int &right)
{
    // readline() changes EasyKids' lastPosition, so evaluate it only once.
    const float error = readline() - setPoint;
    const uint32_t now = millis();
    const float derivative = (!hasPreviousError || (now - lastUpdate) > 100)
        ? 0
        : error - previousError;

    const float output = ((kp / 10) * error) + ((kd / 10) * derivative);
    previousError = error;
    lastUpdate = now;
    hasPreviousError = true;

    left = clamp(leftBaseSpeed - output, -100, 100);
    right = clamp(rightBaseSpeed + output, -100, 100);
}

inline void calculateTrackLine2(int speed, float kp, float kd, int &left, int &right)
{
    calculateTrackLine2LR(speed, speed, kp, kd, left, right);
}

inline bool parseMotorList(const char *motors, int (&selected)[4], int &count)
{
    count = 0;
    if (motors == nullptr || *motors == '\0') {
        return false;
    }

    const char *cursor = motors;
    while (*cursor) {
        if (count >= 4) {
            return false;
        }

        int motorNumber = 0;
        bool hasDigit = false;
        while (*cursor >= '0' && *cursor <= '9') {
            hasDigit = true;
            motorNumber = motorNumber * 10 + (*cursor - '0');
            ++cursor;
        }
        if (!hasDigit || motorNumber < 1 || motorNumber > 4) {
            return false;
        }
        for (int index = 0; index < count; ++index) {
            if (selected[index] == motorNumber) {
                return false;
            }
        }
        selected[count++] = motorNumber;

        if (*cursor == ':') {
            ++cursor;
            if (*cursor == '\0') {
                return false;
            }
        } else if (*cursor) {
            return false;
        }
    }
    return count == 2 || count == 4;
}

}  // namespace cru_car

// Command one physical motor (1 through 4).
inline void trackLine2(int speed, float kp, float kd, int motorNumber)
{
    if (motorNumber < 1 || motorNumber > 4) {
        return;
    }
    int left = 0;
    int right = 0;
    cru_car::calculateTrackLine2(speed, kp, kd, left, right);
    motor(motorNumber, motorNumber <= 2 ? left : right);
}

// A two-motor mapping is left:right; a four-motor mapping is
// left-top:left-bottom:right-top:right-bottom. Examples: "1:2", "1:2:3:4".
inline void trackLine2(int speed, float kp, float kd, const char *motors)
{
    int selected[4];
    int count = 0;
    if (!cru_car::parseMotorList(motors, selected, count)) {
        return;
    }

    int left = 0;
    int right = 0;
    cru_car::calculateTrackLine2(speed, kp, kd, left, right);
    const int leftCount = count / 2;
    for (int index = 0; index < count; ++index) {
        motor(selected[index], index < leftCount ? left : right);
    }
}

// As trackLine2(), but lets each side have its own base speed.
inline void trackLine2LR(int leftBaseSpeed, int rightBaseSpeed, float kp, float kd, int motorNumber)
{
    if (motorNumber < 1 || motorNumber > 4) {
        return;
    }
    int left = 0;
    int right = 0;
    cru_car::calculateTrackLine2LR(leftBaseSpeed, rightBaseSpeed, kp, kd, left, right);
    motor(motorNumber, motorNumber <= 2 ? left : right);
}

// A two-motor mapping is left:right; a four-motor mapping is
// left-top:left-bottom:right-top:right-bottom.
inline void trackLine2LR(int leftBaseSpeed, int rightBaseSpeed, float kp, float kd, const char *motors)
{
    int selected[4];
    int count = 0;
    if (!cru_car::parseMotorList(motors, selected, count)) {
        return;
    }

    int left = 0;
    int right = 0;
    cru_car::calculateTrackLine2LR(leftBaseSpeed, rightBaseSpeed, kp, kd, left, right);
    const int leftCount = count / 2;
    for (int index = 0; index < count; ++index) {
        motor(selected[index], index < leftCount ? left : right);
    }
}