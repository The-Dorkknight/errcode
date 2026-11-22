/* Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
 * Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
 *
 * errcode_ec2.h - single-header EC2 report ENCODER for C/C++ and microcontrollers
 * (ESP32, RP2040, STM32, AVR with enough RAM). No malloc, no floats, ~1 KB of code.
 * The Python package and the HTML decoder read what this writes.
 *
 *   #define ERRCODE_EC2_IMPLEMENTATION   // in exactly one .c/.cpp file
 *   #include "errcode_ec2.h"
 *
 *   ec2_writer w;
 *   ec2_begin(&w, 2, minute, session, "esp-printhost", 2);   // revision, time, session, app, event count
 *   ec2_event_text(&w, 815, EC2_ERROR, 3, "mcu");             // 815 EMB.KLIPPER_LOST_COMM x3, detail "mcu"
 *   ec2_event(&w, 803, EC2_ERROR, 1);                         // 803 EMB.ESP_BROWNOUT
 *   char out[EC2_TEXT_MAX];
 *   ec2_finish(&w, out, sizeof out);                          // "EC2-2054233867..." -> serial / OLED / QR
 *
 * minute = minutes since 2026-01-01 00:00 UTC (pass 0 if the board has no clock).
 * Text details use plain 6-bit symbols (the shared word list is optional for encoders).
 */
#ifndef ERRCODE_EC2_H
#define ERRCODE_EC2_H
#include <stddef.h>
#include <stdint.h>

#ifndef EC2_MAX_BITS
#define EC2_MAX_BITS 2048                     /* ~650 digits: plenty for 20+ events */
#endif
#define EC2_TEXT_MAX (4 + (EC2_MAX_BITS / 63 + 1) * 20 + 1)

enum { EC2_OK = 0, EC2_WARN = 1, EC2_ERROR = 2, EC2_FATAL = 3 };

typedef struct {
    uint8_t bits[(EC2_MAX_BITS + 7) / 8];
    uint32_t nbits;
    int overflow;                             /* set if EC2_MAX_BITS was too small */
} ec2_writer;

#ifdef __cplusplus
extern "C" {
#endif
void ec2_begin(ec2_writer *w, unsigned revision, uint32_t minute, uint16_t session, const char *app,
               unsigned n_events);
void ec2_event(ec2_writer *w, unsigned code, unsigned sev, uint32_t count);
void ec2_event_int(ec2_writer *w, unsigned code, unsigned sev, uint32_t count, int64_t detail);
void ec2_event_text(ec2_writer *w, unsigned code, unsigned sev, uint32_t count, const char *detail);
/* Writes "EC2-<digits>" (NUL-terminated). Returns its length, or 0 if out is too small / overflowed. */
size_t ec2_finish(ec2_writer *w, char *out, size_t out_size);
#ifdef __cplusplus
}
#endif

#ifdef ERRCODE_EC2_IMPLEMENTATION
static void ec2__put(ec2_writer *w, uint64_t v, unsigned n) {
    while (n--) {
        if (w->nbits >= EC2_MAX_BITS) { w->overflow = 1; return; }
        if ((v >> n) & 1u) w->bits[w->nbits >> 3] |= (uint8_t)(0x80u >> (w->nbits & 7));
        w->nbits++;
    }
}
static void ec2__gamma(ec2_writer *w, uint64_t v) {      /* exp-Golomb order 0 */
    uint64_t x = v + 1; unsigned n = 0, i;
    while ((x >> n) > 1) n++;
    for (i = 0; i < n; i++) ec2__put(w, 0, 1);
    ec2__put(w, x, n + 1);
}
static int ec2__sym(char c) {
    static const char punct[] = " ._-/\\:,;=+@()[]'\"~#%&!?";
    int i;
    if (c >= 'a' && c <= 'z') return 4 + (c - 'a');
    if (c >= '0' && c <= '9') return 30 + (c - '0');
    for (i = 0; punct[i]; i++) if (punct[i] == c) return 40 + i;
    return -1;
}
static void ec2__text(ec2_writer *w, const char *s) {
    uint32_t n = 0; const char *p;
    for (p = s; *p; p++) {                                  /* count symbols first */
        char c = *p;
        n += (c >= 'A' && c <= 'Z') ? 2 : 1;                /* SHIFT + letter */
    }
    ec2__gamma(w, n);
    for (p = s; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (c >= 'A' && c <= 'Z') { ec2__put(w, 0, 6); ec2__put(w, (uint64_t)ec2__sym((char)(c - 'A' + 'a')), 6); }
        else if (ec2__sym((char)c) >= 0) ec2__put(w, (uint64_t)ec2__sym((char)c), 6);
        else { ec2__put(w, 3, 6); ec2__put(w, c, 8); }       /* RAW byte */
    }
}
void ec2_begin(ec2_writer *w, unsigned revision, uint32_t minute, uint16_t session, const char *app,
               unsigned n_events) {
    size_t i;
    for (i = 0; i < sizeof w->bits; i++) w->bits[i] = 0;
    w->nbits = 0; w->overflow = 0;
    ec2__gamma(w, revision);
    ec2__put(w, minute & 0x1FFFFFFu, 25);
    ec2__put(w, session & 0x7FFFu, 15);
    ec2__put(w, (app && *app) ? 1 : 0, 1);
    ec2__put(w, 0, 1);                                      /* no log statistics */
    ec2__put(w, 0, 1);                                      /* nothing omitted */
    if (app && *app) ec2__text(w, app);
    ec2__gamma(w, n_events);
}
static void ec2__head(ec2_writer *w, unsigned code, unsigned sev, uint32_t count) {
    ec2__put(w, code > 999 ? 1 : code, 10);
    ec2__put(w, sev & 3u, 2);
    ec2__gamma(w, count ? count - 1 : 0);
}
void ec2_event(ec2_writer *w, unsigned code, unsigned sev, uint32_t count) {
    ec2__head(w, code, sev, count); ec2__put(w, 0, 2);
}
void ec2_event_int(ec2_writer *w, unsigned code, unsigned sev, uint32_t count, int64_t detail) {
    ec2__head(w, code, sev, count);
    if (detail >= 0) { ec2__put(w, 1, 2); ec2__gamma(w, (uint64_t)detail); }
    else { ec2__put(w, 3, 2); ec2__gamma(w, (uint64_t)(-(detail + 1))); }
}
void ec2_event_text(ec2_writer *w, unsigned code, unsigned sev, uint32_t count, const char *detail) {
    ec2__head(w, code, sev, count);
    if (!detail || !*detail) { ec2__put(w, 0, 2); return; }
    ec2__put(w, 2, 2); ec2__text(w, detail);
}
static unsigned ec2__damm(const char *d, size_t n) {
    static const uint8_t t[10][10] = {
        {0,3,1,7,5,9,8,6,4,2},{7,0,9,2,1,5,4,8,6,3},{4,2,0,6,8,7,1,3,5,9},{1,7,5,0,9,8,3,4,2,6},
        {6,1,2,3,0,4,5,9,7,8},{3,6,7,4,2,0,9,5,8,1},{5,8,6,9,7,2,0,1,3,4},{8,9,4,5,3,6,2,0,1,7},
        {9,4,3,8,6,1,7,2,0,5},{2,5,8,1,4,3,6,7,9,0}};
    unsigned i = 0; size_t k;
    for (k = 0; k < n; k++) i = t[i][d[k] - '0'];
    return i;
}
static unsigned ec2__cap(unsigned k) {                      /* bits that k digits always hold */
    static const uint8_t c[20] = {0,3,6,9,13,16,19,23,26,29,33,36,39,43,46,49,53,56,59,63};
    return c[k];
}
size_t ec2_finish(ec2_writer *w, char *out, size_t out_size) {
    size_t o = 4; uint32_t pos = 0;
    if (w->overflow || out_size < 6) return 0;
    out[0] = 'E'; out[1] = 'C'; out[2] = '2'; out[3] = '-';
    while (pos < w->nbits) {
        uint32_t left = w->nbits - pos, take = left >= 63 ? 63 : left;
        unsigned k = 19, nb = 63, i; uint64_t v = 0; char tmp[20];
        if (take < 63) { k = 1; while (ec2__cap(k) < take) k++; nb = ec2__cap(k); }
        for (i = 0; i < take; i++, pos++) v = (v << 1) | ((w->bits[pos >> 3] >> (7 - (pos & 7))) & 1u);
        v <<= (nb - take);
        if (o + k + 2 > out_size) return 0;
        for (i = k; i-- > 0;) { tmp[i] = (char)('0' + (v % 10)); v /= 10; }
        for (i = 0; i < k; i++) out[o++] = tmp[i];
        out[o] = (char)('0' + ec2__damm(out + o - k, k));
        o++;
    }
    out[o] = '\0';
    return o;
}
#endif /* ERRCODE_EC2_IMPLEMENTATION */
#endif /* ERRCODE_EC2_H */
