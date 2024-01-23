from datetime import datetime

import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy.orm import joinedload, contains_eager

from db.base import Session
from db.models import ProfitBundle, ProfitBundleItem, Pair, CoinNetworkExchange, BundleStatus


class SendAnalyticsService:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    HEADER_FIELDS = [
        "From",
        "To",
        "Pair",
        "Network",
        "To Buy",
        "Avg Spread",
        "Base Profit",
        "Total Fee",
        "Profit",
        "Date",
    ]

    def __init__(self, config):
        creds_file_path = "/app/service_account.json"
        credentials = service_account.Credentials.from_service_account_file(creds_file_path, scopes=self.SCOPES)
        self.sheets_service = build("sheets", "v4", credentials=credentials).spreadsheets()
        self.spreadsheet_id = config["GOOGLE_SPREADSHEET_ID"]
        self.sheet_name = self.get_sheet_name()
        self.cell_range = self._get_cell_range()

    def send_to_spreadsheet(self):
        body = {"values": self._get_rows()}
        print(f"body sent - {body}")
        self.sheets_service.values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!{self.cell_range}",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

    def _get_cell_range(self):
        result = (
            self.sheets_service.values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=self.sheet_name,
                majorDimension="ROWS",
            )
            .execute()
        )

        last_row_index = len(result.get("values", []))
        return f"A{last_row_index}:J{last_row_index}"

    def get_sheet_name(self):
        now = datetime.now(pytz.timezone("Europe/Kyiv"))
        sheet_name = now.strftime("%d-%m-%Y")

        spreadsheet = self.sheets_service.get(spreadsheetId=self.spreadsheet_id).execute()
        sheet_exists = any(sheet["properties"]["title"] == sheet_name for sheet in spreadsheet.get("sheets", []))

        if not sheet_exists:
            self._create_sheet(sheet_name)

        return sheet_name

    def _align_by_center(self, sheet_id):
        format_request = {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1000,
                    "startColumnIndex": 0,
                    "endColumnIndex": 11,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                    },
                },
                "fields": "userEnteredFormat.horizontalAlignment",
            },
        }

        self.sheets_service.batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": [format_request]}
        ).execute()

    def _set_header_row(self, sheet_name):
        self.sheets_service.values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{sheet_name}",
            valueInputOption="USER_ENTERED",
            body={"values": [self.HEADER_FIELDS]},
        ).execute()

    def _freeze_header_row(self, sheet_id):
        format_request = {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                    },
                },
                "fields": "gridProperties.frozenRowCount",
            },
        }

        self.sheets_service.batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": [format_request]}
        ).execute()

    def _create_sheet(self, sheet_name):
        response = self.sheets_service.batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()

        sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
        self._align_by_center(sheet_id)
        self._set_header_row(sheet_name)
        self._freeze_header_row(sheet_id)

    @staticmethod
    def get_cell_str_from_utc_datetime(utc_datetime: datetime) -> str:
        date = utc_datetime.replace(tzinfo=pytz.UTC)
        date = date.astimezone(pytz.timezone("Europe/Kyiv"))
        return date.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_utc_datetime_from_cell_str(date_str: str) -> [datetime, None]:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        date = date.replace(tzinfo=pytz.timezone("Europe/Kyiv"))
        date = date.astimezone(pytz.UTC)

        return date

    def _get_rows(self):
        rows = []

        with Session() as session:
            to_sync_bundle_ids_subq = session.query(ProfitBundle.id).filter(
                ProfitBundle.status == BundleStatus.done, ProfitBundle.synced.is_(False)
            )

            bundles_qs = (
                session.query(ProfitBundle)
                .join(ProfitBundle.items)
                .filter(ProfitBundle.id.in_(to_sync_bundle_ids_subq))
                .options(
                    contains_eager(ProfitBundle.items),
                    joinedload(ProfitBundle.coin_network_exchange),
                    joinedload(ProfitBundle.coin_network_exchange).joinedload(CoinNetworkExchange.network),
                    joinedload(ProfitBundle.pair),
                    joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                    joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                    joinedload(ProfitBundle.base_exchange),
                    joinedload(ProfitBundle.pair_exchange),
                )
                .order_by(ProfitBundle.created_at, ProfitBundleItem.created_at)
            )

            for bundle in bundles_qs:
                rows.extend([[]])
                for bundle_item in bundle.items:
                    created_date = self.get_cell_str_from_utc_datetime(bundle_item.created_at)
                    row = [
                        bundle.base_exchange.name,
                        bundle.pair_exchange.name,
                        bundle.pair.default_name,
                        bundle.coin_network_exchange.network.name,
                        round(bundle_item.to_use_usdt, 3),
                        f"{round(bundle_item.avg_spread * 100, 3)}%",
                        round(bundle_item.base_profit, 3),
                        round(bundle_item.total_fee, 3),
                        round(bundle_item.profit, 3),
                        created_date,
                    ]
                    rows.append(row)

            session.query(ProfitBundle).filter(ProfitBundle.id.in_(to_sync_bundle_ids_subq)).update(
                {"synced": True}, synchronize_session=False
            )
            session.commit()

        return rows
