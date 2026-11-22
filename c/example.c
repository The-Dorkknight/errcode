/* Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
 * Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
 * Build: cc -O2 -o ec2_example example.c && ./ec2_example
 * Then decode the printed line: errcode decode "EC2-..." (or paste it into decode.html). */
#include <stdio.h>
#define ERRCODE_EC2_IMPLEMENTATION
#include "errcode_ec2.h"

int main(void) {
    ec2_writer w;
    char out[EC2_TEXT_MAX];
    ec2_begin(&w, 2, 444000u, 12345u, "esp-printhost", 4);
    ec2_event_text(&w, 815, EC2_ERROR, 3, "mcu");          /* EMB.KLIPPER_LOST_COMM x3 */
    ec2_event(&w, 803, EC2_ERROR, 1);                      /* EMB.ESP_BROWNOUT */
    ec2_event_int(&w, 43, EC2_ERROR, 1, -11);              /* GEN.EXIT_NONZERO, detail -11 */
    ec2_event_text(&w, 101, EC2_ERROR, 1, "PyQt6 <x>");    /* PY.MODULE_MISSING, upper case + raw chars */
    if (!ec2_finish(&w, out, sizeof out)) { fputs("buffer too small\n", stderr); return 1; }
    puts(out);
    return 0;
}
