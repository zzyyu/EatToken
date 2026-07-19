FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
COPY . .
EXPOSE 8080
CMD ["eat-token", "web", "--host", "0.0.0.0"]
