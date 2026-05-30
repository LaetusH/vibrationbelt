#pragma once
#include <Arduino.h>

// --- Konfiguration -------------------------------------------
const int MOTOR_PINS[]   = {32, 33};
const int MOTOR_COUNT    = 2;
const int PWM_FREQ       = 1000;
const int PWM_RESOLUTION = 8;

// --- Forward declarations ------------------------------------
void hilfe_anzeigen();
void status_anzeigen();

// --- Motor-Struktur ------------------------------------------
struct Motor {
  int  pin;
  int  staerke;
  bool aktiv;
};

Motor motoren[MOTOR_COUNT];

// --- Setup ---------------------------------------------------
void motoren_setup() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    motoren[i].pin     = MOTOR_PINS[i];
    motoren[i].staerke = 0;
    motoren[i].aktiv   = false;
    ledcAttach(motoren[i].pin, PWM_FREQ, PWM_RESOLUTION);
    ledcWrite(motoren[i].pin, 0);
  }
}

// --- Motor einzeln setzen ------------------------------------
void motor_setzen(int index, int prozent) {
  prozent = constrain(prozent, 0, 100);
  motoren[index].staerke = prozent;
  motoren[index].aktiv   = (prozent > 0);
  ledcWrite(motoren[index].pin, map(prozent, 0, 100, 0, 255));
  Serial.print("Motor "); Serial.print(index + 1);
  Serial.print(" -> ");   Serial.print(prozent); Serial.println("%");
}

void alle_setzen(int prozent) {
  for (int i = 0; i < MOTOR_COUNT; i++) motor_setzen(i, prozent);
}

void alle_stoppen() {
  alle_setzen(0);
  Serial.println("Alle Motoren gestoppt.");
}

// --- Befehl verarbeiten --------------------------------------
void befehl_verarbeiten(String eingabe) {
  eingabe.trim();
  eingabe.toLowerCase();
  if (eingabe == "hilfe" || eingabe == "h")  { hilfe_anzeigen(); return; }
  if (eingabe == "status" || eingabe == "s") { status_anzeigen(); return; }
  if (eingabe == "alle stop")                { alle_stoppen(); return; }
  if (eingabe.startsWith("alle ")) {
    alle_setzen(eingabe.substring(5).toInt());
    return;
  }
  if (eingabe.startsWith("m") && eingabe.length() >= 4) {
    int index = eingabe.charAt(1) - '1';
    int wert  = eingabe.substring(3).toInt();
    if (index >= 0 && index < MOTOR_COUNT) motor_setzen(index, wert);
    else Serial.println("Unbekannter Motor. Nutze m1 oder m2.");
    return;
  }
  Serial.println("Unbekannter Befehl. Tippe 'hilfe'.");
}

// --- Status --------------------------------------------------
void status_anzeigen() {
  Serial.println("--- Status ---");
  for (int i = 0; i < MOTOR_COUNT; i++) {
    Serial.print("Motor "); Serial.print(i + 1);
    Serial.print(" (GPIO "); Serial.print(motoren[i].pin); Serial.print("): ");
    Serial.print(motoren[i].staerke); Serial.print("%  ");
    Serial.println(motoren[i].aktiv ? "[AN]" : "[AUS]");
  }
  Serial.println("--------------");
}

// --- Hilfe ---------------------------------------------------
void hilfe_anzeigen() {
  Serial.println("=====================================");
  Serial.println("  Vibrations-Motor Steuerung v1.0");
  Serial.println("=====================================");
  Serial.println("  m1 <0-100>   Motor 1 setzen");
  Serial.println("  m2 <0-100>   Motor 2 setzen");
  Serial.println("  alle <0-100> Beide setzen");
  Serial.println("  alle stop    Alle stoppen");
  Serial.println("  status       Zustand anzeigen");
  Serial.println("  hilfe        Diese Uebersicht");
  Serial.println("=====================================");
}
