# A Data Volume Container to persist the expensively built virtualenv across
# rebuilds of the "dev" image

# Same base as dev image, to save space. (It's copy-on-write.)
FROM ubuntu@sha256:0ca448cb174259ddb2ae6e213ebebe7590862d522fe38971e1175faedf0b6823

# Match UID with dev image:
RUN mkdir /venv && chown -R 1000:1000 /venv
VOLUME /venv
