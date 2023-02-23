// @ts-ignore
import React, { FC, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "antd";
import { useMutation, useQuery } from "react-query";
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import { Netsuite } from "../../api/api";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;
const downloadFile = async (s3link) => {
  if (!s3link) {
    toast.error("No file to download");
    return;
  }
  console.log("s3link", s3link);
  window.open(s3link);
};

// create FC component called BraintreeIntegration
const NetsuiteIntegrationView: FC = () => {
  // create variable called {id} and set it to type string
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const getInvoicesCSV = async () => {
    try {
      const response = await Netsuite.invoices();
      console.log("response", response);
      const csvUrl = response.url;
      console.log("csvUrl", csvUrl);
      downloadFile(csvUrl);
    } catch (err) {
      toast.error("Error downloading file");
    }
  };

  // create variable called returnToDashboard and set it to type void
  const returnToDashboard = () => {
    navigate(-1);
  };

  // create return statement
  return (
    <PageLayout
      title="Netsuite Integration"
      extra={<Button onClick={returnToDashboard}>Back to Integrations</Button>}
    >
      <div className="w-6/12">
        <h3 className="text-16px mb-10">Generate Invoice CSVs for Netsuite</h3>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-6 py-10">
          <h3>Download Invoices CSV:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => getInvoicesCSV()}
          >
            Download
          </Button>
        </div>
        <div className="seperator" />
        <div />
      </div>
    </PageLayout>
  );
};

export default NetsuiteIntegrationView;
