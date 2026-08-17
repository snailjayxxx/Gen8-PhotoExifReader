#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <unistd.h>

static void send_all(int fd, const char *buf, size_t len) {
    while (len > 0) {
        ssize_t n = send(fd, buf, len, 0);
        if (n <= 0) return;
        buf += n;
        len -= (size_t)n;
    }
}

static void html_escape(const char *src, char *dst, size_t cap) {
    size_t j = 0;
    for (size_t i = 0; src && src[i] && j + 8 < cap; ++i) {
        const char *rep = NULL;
        switch (src[i]) {
            case '&': rep = "&amp;"; break;
            case '<': rep = "&lt;"; break;
            case '>': rep = "&gt;"; break;
            case '"': rep = "&quot;"; break;
            default: dst[j++] = src[i]; continue;
        }
        size_t n = strlen(rep);
        memcpy(dst + j, rep, n);
        j += n;
    }
    dst[j] = '\0';
}

int main(int argc, char **argv) {
    int port = argc > 1 ? atoi(argv[1]) : 9865;
    const char *raw_reason = argc > 2 ? argv[2] : "Python runtime unavailable";
    char reason[512];
    html_escape(raw_reason, reason, sizeof(reason));

    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return 2;
    int one = 1;
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons((unsigned short)port);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) != 0) return 3;
    if (listen(s, 16) != 0) return 4;

    struct utsname u;
    memset(&u, 0, sizeof(u));
    uname(&u);

    for (;;) {
        int c = accept(s, NULL, NULL);
        if (c < 0) {
            if (errno == EINTR) continue;
            break;
        }
        char req[2048];
        ssize_t r = recv(c, req, sizeof(req) - 1, 0);
        if (r < 0) r = 0;
        req[r] = '\0';
        int health = strstr(req, "GET /api/health ") != NULL;
        char body[12288];
        if (health) {
            snprintf(body, sizeof(body),
                "{\"ok\":true,\"version\":\"0.1.1-0003\",\"mode\":\"native-diagnostic\",\"machine\":\"%s\"}", u.machine);
        } else {
            snprintf(body, sizeof(body),
                "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>摄影 EXIF 档案</title>"
                "<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f4f7fb;color:#172033;margin:0}.wrap{max-width:820px;margin:48px auto;padding:24px}.card{background:#fff;border-radius:16px;padding:28px;box-shadow:0 8px 30px rgba(0,0,0,.08)}.ok{color:#16803c;font-weight:700}.warn{color:#a45b00}.mono{font-family:monospace;background:#f3f5f8;padding:2px 6px;border-radius:6px}.reason{padding:14px;background:#fff7e8;border-radius:10px}</style></head>"
                "<body><div class=\"wrap\"><div class=\"card\"><h1>摄影 EXIF 档案</h1><p class=\"ok\">✓ DSM 套件服务已经成功启动</p>"
                "<p>当前运行的是 <b>v0.1.1-0003 原生诊断模式</b>。这证明 SPK 安装、启动脚本、服务状态与 9865 端口链路正常。</p>"
                "<p class=\"reason\"><b>Python 后端未启动的原因：</b><br>%s</p>"
                "<p>系统：<span class=\"mono\">%s %s</span> 架构：<span class=\"mono\">%s</span></p>"
                "<p class=\"warn\">请把这个页面截图发回，我就能针对实际运行时继续制作完整 EXIF 版。</p></div></div></body></html>",
                reason, u.sysname, u.release, u.machine);
        }
        const char *ct = health ? "application/json" : "text/html";
        char hdr[512];
        int n = snprintf(hdr, sizeof(hdr),
            "HTTP/1.1 200 OK\r\nContent-Type: %s; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: %zu\r\n\r\n", ct, strlen(body));
        send_all(c, hdr, (size_t)n);
        send_all(c, body, strlen(body));
        close(c);
    }
    close(s);
    return 0;
}
