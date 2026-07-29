# Alpine 3.22 is here for one reason: it ships OpenSSL 3.5, which is the first
# version that knows the X25519MLKEM768 group. On anything older every site comes
# back classical and the endpoint quietly lies. /api/health reports which openssl
# it found and whether it can see the group, so check that first if the numbers
# look wrong.
FROM alpine:3.22

# curl, dig and whois are the three signals detect_cdn() uses, in that order.
RUN apk add --no-cache python3 py3-pip openssl curl bind-tools whois

WORKDIR /app
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /app/api/requirements.txt

# the API imports scan.py, readiness_score.py and cdn_attribution.py from the
# dashboard folder above it, and reads data/ for the corpus, so the build context
# is the dashboard folder, not api/:
#     docker build -f api/Dockerfile -t pqc-scan .
COPY . /app

WORKDIR /app/api
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
