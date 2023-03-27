import React, { FC, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button, DatePicker } from "antd";
import moment from "moment";
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import { Netsuite } from "../../api/api";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;
const downloadFile = async (s3link: URL) => {
  if (!s3link) {
    toast.error("No file to download");
    return;
  }
  window.open(s3link);
};

const NetsuiteIntegrationView: FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [startDate, setStartDate] = useState<moment.Moment | null>(null);
  const [endDate, setEndDate] = useState<moment.Moment | null>(null);

  const getInvoicesCSV = async () => {
    try {
      const response = await Netsuite.invoices(
        startDate?.toDate(),
        endDate?.toDate()
      );
      const csvUrl = response.url;
      downloadFile(csvUrl);
    } catch (err) {
      toast.error("Error downloading file");
    }
  };

  const getCustomersCSV = async () => {
    try {
      const response = await Netsuite.customers(
        startDate?.toDate(),
        endDate?.toDate()
      );
      const csvUrl = response.url;
      downloadFile(csvUrl);
    } catch (err) {
      toast.error("Error downloading file");
    }
  };

  const returnToDashboard = () => {
    navigate(-1);
  };

  return (
    <PageLayout
      title="Netsuite Integration"
      extra={<Button onClick={returnToDashboard}>Back to Integrations</Button>}
    >
      <div className="w-6/12">
        <h3 className="text-16px mb-10">Generate Invoice CSVs for Netsuite</h3>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-6 py-10">
          <h3>Select date range:</h3>
          <DatePicker.RangePicker
            className="w-6/12"
            value={[startDate, endDate]}
            allowEmpty={[true, true]}
            onChange={(dates) => {
              if (dates) {
                setStartDate(dates[0]);
                setEndDate(dates[1]);
              } else {
                setStartDate(null);
                setEndDate(null);
              }
            }}
          />
          <h3>Download Invoices CSV:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => getInvoicesCSV()}
          >
            Download
          </Button>
          {/* <h3>Download Customers CSV:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => getCustomersCSV()}
          >
            Download
          </Button> */}
        </div>
        <div className="seperator" />
        <div />
      </div>
    </PageLayout>
  );
};

export default NetsuiteIntegrationView;
