from flask import Flask, request, Response, redirect, url_for, render_template, flash, get_flashed_messages
import webbrowser
from mtgproxies.decklists import parse_decklist, parse_decklist_stream
from io import TextIOWrapper, StringIO
import scryfall

app = Flask(__name__)
session = {}  # Poor man's session: server-side and not dropping randomly


@app.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'POST':
        if 'decklist' in session:
            del session['decklist']

        decklist_file = request.files['decklist_file']
        if decklist_file.filename != '':
            decklist, ok, warnings = parse_decklist_stream(TextIOWrapper(decklist_file))
        elif request.form['decklist'] != '':
            decklist, ok, warnings = parse_decklist_stream(StringIO(request.form['decklist']))
        else:
            flash('ERROR: No decklist provided')
            return redirect(request.url)

        if not ok:
            for _, warning in warnings:
                flash(warning)
        elif len(decklist.cards) == 0:
            flash('ERROR: Decklist is empty')
            ok = False

        if ok:
            session['decklist'] = decklist
            session['alternatives'] = [scryfall.recommend_print(card, mode="choices") for card in decklist.cards]
            return redirect(url_for('show'))
        decklist_str = format(decklist, "arena")
    elif 'decklist' in session:
        decklist_str = format(session['decklist'], "arena")
    else:
        decklist_str = ""

    warnings = []
    errors = []
    for message in get_flashed_messages():
        if message[:7] == "WARNING":
            warnings.append(message[9:])
        elif message[:5] == "ERROR":
            errors.append(message[7:])

    return render_template(
        'start.html',
        decklist=decklist_str,
        decklist_ok='decklist' in session,
        warnings=warnings,
        errors=errors,
    )


@app.route('/show')
def show():
    if 'decklist' not in session:
        return redirect(url_for("start"))

    cards = []
    for i, card in enumerate(session['decklist'].cards):
        faces = [
            {
                "img_preview": image_uri['normal'],
                "img_large": image_uri['png'],
            } for image_uri in card.image_uris
        ]
        cards.append(
            {
                "name": f"{card['name']} ({card['set'].upper()}) {card['collector_number']}",
                "change_url": url_for("choice", idx=i),
                "faces": faces,
                "alternatives": len(session['alternatives'][i]) - 1,
                "idx": i,
            }
        )

    return render_template('show.html', cards=cards, idx=request.args.get('idx'), decklist_ok=True)


@app.route('/choice/<int:idx>')
def choice(idx):
    if 'decklist' not in session:
        return redirect(url_for("start"))

    cur = session['decklist'].cards[idx]
    cards = []
    for i, card in enumerate(scryfall.recommend_print(cur, mode="choices")):
        image_uris = [face["image_uris"] for face in scryfall.get_faces(card)]
        faces = [{
            "img_preview": image_uri['normal'],
            "img_large": image_uri['png'],
        } for image_uri in image_uris]
        cards.append(
            {
                "name": f"{card['name']} ({card['set'].upper()}) {card['collector_number']}",
                "change_url": url_for("update", idx=idx, update=i) if i > 0 else url_for("show", idx=idx),
                "faces": faces,
            }
        )

    return render_template('choose.html', cards=cards, decklist_ok=True)


@app.route('/update/<int:idx>/<int:update>')
def update(idx, update):
    # Replace print in  decklist
    entry = session['decklist'].cards[idx]
    entry.card = scryfall.recommend_print(entry.card, mode="choices")[update]

    # Update cache
    session['alternatives'][idx] = scryfall.recommend_print(entry, mode="choices")

    # Return to overview
    return redirect(url_for("show", idx=idx))


@app.route('/download')
def download():
    if 'decklist' not in session:
        return redirect(url_for("start"))

    return render_template(
        'download.html',
        decklist=format(session['decklist'], "arena"),
        decklist_ok=True,
    )


if __name__ == "__main__":
    import os
    import argparse

    parser = argparse.ArgumentParser(description='Starts a local webserver providing a GUI.')
    parser.add_argument('--port', help='output format (default: %(default)s)', type=int, default=5000)
    args = parser.parse_args()

    print("Initializing database ...")
    scryfall.get_cards(id="")  # Dummy query

    app.secret_key = os.urandom(24)
    webbrowser.open(f'http://127.0.0.1:{args.port}/start')
    print("Starting webserver ...")
    app.run(port=args.port)
