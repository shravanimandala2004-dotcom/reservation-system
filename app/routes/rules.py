from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Rule

rules_bp = Blueprint('rules', __name__, url_prefix='/rules')

@rules_bp.route('/')
def rules():
    return render_template('rules.html')
# @rules_bp.route('/', methods=['GET', 'POST'])

# def rules():
#     rules = Rule.query.all()

#     # Admin can add rules
#     if request.method == 'POST' and current_user.is_admin:
#         new_rule = Rule(content=request.form['rule'])
#         db.session.add(new_rule)
#         db.session.commit()
#         return redirect(url_for('rules.rules'))

#     return render_template('rules.html', rules=rules)

# @rules_bp.route('/delete/<int:rule_id>', methods=['POST'])

# def delete_rule(rule_id):
#     if current_user.is_admin:
#         rule = Rule.query.get(rule_id)
#         db.session.delete(rule)
#         db.session.commit()
#     return redirect(url_for('rules.rules'))

