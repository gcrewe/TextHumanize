# TextHumanize Actor image.
# Builds on the official Apify Python base image and installs the texthumanize
# library straight from this repository, so the Actor runs the checked-out code.
FROM apify/actor-python:3.13

# Install dependencies first: this layer is reused between builds unless
# requirements.txt changes.
COPY --chown=myuser:myuser requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && pip --version \
 && echo "Installing dependencies:" \
 && pip install --no-cache-dir -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

# Copy the Actor sources and the texthumanize library.
COPY --chown=myuser:myuser . ./

# Install the library from this repository and pre-compile the Actor code.
RUN pip install --no-cache-dir -e . \
 && python -m compileall -q text_humanize_actor/

CMD ["python", "-m", "text_humanize_actor"]
