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
            flash('No decklist provided')
            return redirect(request.url)

        if not ok:
            for _, warning in warnings:
                flash(warning)
        elif len(decklist.cards) == 0:
            flash('Decklist is empty')
            ok = False

        session['decklist'] = decklist
        session['decklist_ok'] = ok
        if ok:
            return redirect(url_for('show'))

    decklist_str = format(session['decklist'], "arena") if 'decklist' in session else ""
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
        warnings=warnings,
        errors=errors,
    )


@app.route('/show')
def show():
    if 'decklist' not in session:
        return Response("Missing decklist in session", status=201)

    from tqdm import tqdm
    cards = []
    for i, card in tqdm(enumerate(session['decklist'].cards)):
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
                "alternatives": len(scryfall.recommend_print(card, mode="choices")) - 1
            }
        )

    return render_template('show.html', cards=cards)


@app.route('/choice/<int:idx>')
def choice(idx):
    cur = session['decklist'].cards[idx]
    cards = []
    for i, card in enumerate(scryfall.recommend_print(cur["name"], mode="choices")):
        image_uris = [face["image_uris"] for face in scryfall.get_faces(card)]
        faces = [{
            "img_preview": image_uri['normal'],
            "img_large": image_uri['png'],
        } for image_uri in image_uris]
        cards.append(
            {
                "name": f"{card['name']} ({card['set'].upper()}) {card['collector_number']}",
                "change_url": url_for("show"),
                "faces": faces,
            }
        )

    return render_template('choose.html', cards=cards)


if __name__ == "__main__":
    import os
    import argparse

    parser = argparse.ArgumentParser(description='Starts a local webserver providing a GUI.')
    parser.add_argument('decklist', help='a decklist file (default: %(default)s)', nargs='?', default=None)
    parser.add_argument('--port', help='output format (default: %(default)s)', type=int, default=5000)
    args = parser.parse_args()

    # Parse decklist
    if args.decklist is not None:
        decklist, ok = parse_decklist(args.decklist)
        if not ok:
            print("Decklist contains invalid card names. Fix errors above before reattempting.")
            quit()

        print("Found %d cards in total with %d unique cards." % (
            decklist.total_count,
            decklist.total_count_unique,
        ))

    app.secret_key = os.urandom(24)
    webbrowser.open(f'http://127.0.0.1:{args.port}/start')
    app.run(port=args.port)
