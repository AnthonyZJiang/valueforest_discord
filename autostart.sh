git pull

venv=.venv/bin/

if [[ -d "${venv}" && ! -L "${venv}" ]]; then
	source ${venv}/activate
else
	echo "venv not found."
fi

if [[ "$1" == "-U" ]]; then
	pip install -U -r requirements.txt
	shift
fi

python3 run_bot.py "$@"  # Pass all arguments to run_bot.py
