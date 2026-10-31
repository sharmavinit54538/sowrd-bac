import sqlalchemy as sa
from app.core.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profile"

    id = sa.Column(sa.Integer, primary_key=True, default=1)
    name = sa.Column(sa.String(255), nullable=False, default="SWORD INNOVATIONS")
    tagline = sa.Column(sa.String(255), nullable=True)
    address = sa.Column(sa.Text, nullable=False)
    city = sa.Column(sa.String(100), nullable=False, default="Jaipur")
    state_name = sa.Column(sa.String(100), nullable=False, default="Rajasthan")
    state_code = sa.Column(sa.String(10), nullable=False, default="08")
    gstin = sa.Column(sa.String(20), nullable=False, default="08AGIPN6872D1Z4")
    pan = sa.Column(sa.String(20), nullable=False, default="AGIPN6872D")
    iec = sa.Column(sa.String(20), nullable=False, default="AGIPN6872D")
    phones = sa.Column(sa.JSON, nullable=False, default=list)
    email = sa.Column(sa.String(255), nullable=False, default="sales@swordinn.biz")
    founder = sa.Column(sa.String(100), nullable=True)
    founder_mobile = sa.Column(sa.String(50), nullable=True)
    jurisdiction = sa.Column(sa.String(100), nullable=False, default="Jaipur")

