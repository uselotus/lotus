# Create a builder stage
FROM golang:alpine as builder

RUN apk update
RUN apk add --no-cache git ca-certificates \
    && update-ca-certificates

ENV USER=appuser
ENV UID=10001 

RUN adduser \    
    --disabled-password \    
    --gecos "" \    
    --home "/nonexistent" \    
    --shell "/sbin/nologin" \    
    --no-create-home \    
    --uid "${UID}" \    
    "${USER}"


RUN mkdir src/app
WORKDIR /src/app
COPY . .

# Fetch dependencies
RUN go mod download
RUN go mod verify

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-w -s" \
    -o /go/bin/docker-binary

# Create clean image
FROM scratch

# Copy only the static binary
COPY --from=builder \
    /go/bin/docker-binary \
    /go/bin/docker-binary
COPY --from=builder \
    /etc/ssl/certs/ca-certificates.crt \
    /etc/ssl/certs/
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

# Use our user!
USER appuser:appuser

# Run the binary
ENTRYPOINT ["/go/bin/docker-binary"]