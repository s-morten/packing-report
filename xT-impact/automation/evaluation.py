#!/usr/bin/python

from handlers_packing import EvalHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import json

eval_handler = EvalHandler()
eval = eval_handler.get_eval()

def sendMail(subject, text):

    senderEmail = "mortenstehr@hotmail.de"
    empfangsEmail = "mortensportwetten@gmail.com"
    msg = MIMEMultipart()
    msg["From"] = senderEmail
    msg["To"] = empfangsEmail
    msg["Subject"] = subject
    sender_pass = json.load(open("/home/morten/Develop/packing-report/xT-impact/automation/mail-secret.json", "r"))["password"]
    emailText = text
    msg.attach(MIMEText(emailText, "plain"))

    server = smtplib.SMTP("smtp.office365.com", 587)  # Die Server Daten
    server.starttls()
    server.login(
        senderEmail,
        sender_pass
    )  # Das Passwort
    text = msg.as_string()
    server.sendmail(senderEmail, empfangsEmail, text)
    server.quit()

# create mail string
text = ""
text += "Weekly Evaluation: \n"
text += f"Total games: {eval.all_time_evaluation.num_bets} \n"
text += "  -----  \n"
text += f"Total bets: {eval.all_time_evaluation.num_bets}\n"
text += f"Total bets won: {eval.all_time_evaluation.num_bets_won}, {eval.all_time_evaluation.num_bets_won / eval.all_time_evaluation.num_bets}\n"
text += f"Total money won: {eval.all_time_evaluation.money_won}\n"
text += "  -----  \n"
text += f"Bets home: {eval.all_time_evaluation.num_bets_home}, {eval.all_time_evaluation.num_bets_home / eval.all_time_evaluation.num_bets}\n"
text += f"Bets home won {eval.all_time_evaluation.num_bets_home_won}, {eval.all_time_evaluation.num_bets_home_won / eval.all_time_evaluation.num_bets_home}\n"
text += f"Bets home money won {eval.all_time_evaluation.money_won_home}\n"
text += "  -----  \n"
text += f"Bets draw: {eval.all_time_evaluation.num_bets_draw}, {eval.all_time_evaluation.num_bets_draw / eval.all_time_evaluation.num_bets}\n"
text += f"Bets draw won {eval.all_time_evaluation.num_bets_draw_won}, {eval.all_time_evaluation.num_bets_draw_won / eval.all_time_evaluation.num_bets_draw}\n"
text += f"Bets draw money won {eval.all_time_evaluation.money_won_draw}\n"
text += "  -----  \n"
text += f"Bets away: {eval.all_time_evaluation.num_bets_away}, {eval.all_time_evaluation.num_bets_away / eval.all_time_evaluation.num_bets}\n"
text += f"Bets away won {eval.all_time_evaluation.num_bets_away_won}, {eval.all_time_evaluation.num_bets_away_won / eval.all_time_evaluation.num_bets_away}\n"
text += f"Bets away money won {eval.all_time_evaluation.money_won_away}\n"
text += "  -----  "

sendMail("Weekly Report", text)