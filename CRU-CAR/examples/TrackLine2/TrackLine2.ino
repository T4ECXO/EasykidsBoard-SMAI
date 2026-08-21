#include <CRU_CAR.h>

void setup()
{
  EasyKids_Setup();
  sensorNum(6);
}

void loop()
{
  // Two motors: left:right. Base speeds are left=40, right=30.
  trackLine2LR(40, 30, 1.0, 1.0, "1:2");

  // For four motors use: trackLine2LR(40, 30, 1.0, 1.0, "1:2:3:4");
}
