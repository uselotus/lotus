import React, { FC, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button, Switch } from "antd";
import moment from "moment";
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import { CRM } from "../../api/api";
import useGlobalStore from "../../stores/useGlobalstore";
import {
  CRMConnectionStatus,
  CRMProviderType,
  CRMSetting,
} from "../../types/crm-types";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;
const SalesforceIntegrationView: FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const org = useGlobalStore((state) => state.org);

  const returnToDashboard = () => {
    navigate(-1);
  };

  const getCRMSettings = async (): Promise<CRMSetting[]> =>
    CRM.getCRMSettings({ setting_group: "crm" });
  const {
    error,
    data: crmSettings,
    isLoading: crmSettingsLoading,
    refetch: refetchCRMSettings,
  } = useQuery<CRMSetting[]>(["crm_settings"], getCRMSettings);

  const [isChecked, setIsChecked] = useState<boolean>(false); // added state for toggle

  useEffect(() => {
    const crmCustomerSourceSetting = crmSettings?.find(
      (setting) => setting.setting_name === "crm_customer_source"
    );
    const crmCustomerSourceSettings =
      crmCustomerSourceSetting?.setting_values as Record<
        CRMProviderType,
        boolean
      >;
    const isLotusSource = crmCustomerSourceSettings?.salesforce || false;

    const isSalesforceSource = !isLotusSource;
    setIsChecked(isSalesforceSource);
  }, [crmSettings]);

  const handleToggleChange = (checked: boolean) => {
    // add method to call backend
    const crm_provider_name = "salesforce";
    const salesforce_is_source = checked;
    const lotus_is_source = !salesforce_is_source;
    CRM.setCustomerSourceOfTruth(crm_provider_name, lotus_is_source)
      .then((response) => {
        toast.success(
          `Customer Information Source of Truth set to ${
            checked ? "Salesforce" : "Lotus"
          }`
        );
        setIsChecked(checked);
        refetchCRMSettings();
      })
      .catch((err) => {
        toast.error("Error setting customer information source of truth");
      });
  };

  const handleSyncCRM = () => {
    CRM.syncCRM(org.organization_id, ["salesforce"])
      .then((response) => {
        if (response.success) {
          toast.success(response.message, { position: TOAST_POSITION });
        } else {
          toast.error(response.message, { position: TOAST_POSITION });
        }
      })
      .catch((err) => {
        toast.error("Error syncing CRM data", { position: TOAST_POSITION });
      });
  };

  return (
    <PageLayout
      title="Salesforce Integration"
      extra={<Button onClick={returnToDashboard}>Back to Integrations</Button>}
    >
      <div className="w-6/12">
        <h3 className="text-16px mb-10">
          Sync Customers, Invoices, and Subscriptions
        </h3>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-6 py-10">
          <h3 className="text-16px font-semibold mb-2">
            Customer Information Source of Truth:
          </h3>
          <div className="flex items-center">
            <span className="mr-4 text-sm font-medium">Lotus</span>
            <Switch checked={isChecked} onChange={handleToggleChange} />
            <span className="ml-4 text-sm font-medium">Salesforce</span>
          </div>
          <h3>Sync Now:</h3>
          <Button size="large" className="w-4/12" onClick={handleSyncCRM}>
            Sync
          </Button>
        </div>
        <p className="text-darkgold mb-4">
          Source of truth applies to the following fields: Name, Addresses.
          Lotus Customers will be synced with Salesforce Accounts, and IDs will
          be pulled from the Account Number field in the Account Information
          section. If not found Salesforce Account ID will be used.
        </p>
        <div className="seperator" />
        <div />
      </div>
    </PageLayout>
  );
};

export default SalesforceIntegrationView;
