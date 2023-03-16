/* eslint-disable no-shadow */

import React, { FC, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import { PaymentProcessor } from "../../api/api";
import {
  PaymentProcessorSetting,
  Source,
  PaymentProcessorImportCustomerResponse,
  UpdatePaymentProcessorSettingParams,
} from "../../types/payment-processor-type";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;

// create FC component called BraintreeIntegration
const BraintreeIntegrationView: FC = () => {
  const navigate = useNavigate();
  const [isSettingValue, setIsSettingValue] = useState(false);
  const [currentBraintreeSetting, setCurrentBraintreeSetting] =
    useState<PaymentProcessorSetting>();

  const getBraintreeSettings = async (): Promise<PaymentProcessorSetting[]> =>
    PaymentProcessor.getPaymentProcessorSettings({
      setting_group: "braintree",
    });

  const { error, data, isLoading } = useQuery<PaymentProcessorSetting[]>(
    ["braintree_settings"],
    getBraintreeSettings
  );

  useEffect(() => {
    if (!isLoading && !error && data) {
      setCurrentBraintreeSetting(
        data.filter(
          (item) => item.setting_name === "gen_cust_in_braintree_after_lotus"
        )[0]
      );
    }
  }, [isLoading, error, data]);

  const importCustomersMutation = useMutation(
    (post: Source) => PaymentProcessor.importCustomers(post),
    {
      onSuccess: (data: PaymentProcessorImportCustomerResponse) => {
        toast.success(data.detail, {
          position: TOAST_POSITION,
        });
      },
      onError: () => {
        toast.error("Failed to Import Customers", {
          position: TOAST_POSITION,
        });
      },
    }
  );

  // const importPaymentsMutation = useMutation(
  //   (post: Source) => PaymentProcessor.importPayments(post),
  //   {
  //     onSuccess: (data: PaymentProcessorImportCustomerResponse) => {
  //       toast.success(data.detail, {
  //         position: TOAST_POSITION,
  //       });
  //     },

  //     onError: () => {
  //       toast.error("Failed to Import Payments", {
  //         position: TOAST_POSITION,
  //       });
  //     },
  //   }
  // );

  // const resolveAfter3Sec = new Promise((resolve) => setTimeout(resolve, 3000));

  // const transferSubscriptionsMutation = useMutation(
  //   (post: TransferSub) => PaymentProcessor.transferSubscriptions(post),
  //   {
  //     onSuccess: (data: PaymentProcessorImportCustomerResponse) => {
  //       toast.success(data.detail, {
  //         position: TOAST_POSITION,
  //       });
  //     },
  //     onError: () => {
  //       toast.error("Failed to transfer subscriptions", {
  //         position: TOAST_POSITION,
  //       });
  //     },
  //   }
  // );

  const updateBraintreeSettings = useMutation(
    (post: UpdatePaymentProcessorSettingParams) =>
      PaymentProcessor.updatePaymentProcessorSetting(post),
    {
      onSuccess: (data: PaymentProcessorSetting) => {
        setCurrentBraintreeSetting(data);
        setIsSettingValue(false);
        const state =
          data.setting_values.value === true ? "Enabled" : "Disabled";
        toast.success(`${state} Create Lotus Customers In Braintree`, {
          position: TOAST_POSITION,
        });
      },
      onError: () => {
        setIsSettingValue(false);
        toast.error("Failed to Update Create Lotus Customers In Braintree", {
          position: TOAST_POSITION,
        });
      },
    }
  );

  // promises to handle toast loading messages

  // create variable called returnToDashboard and set it to type void
  const returnToDashboard = () => {
    navigate(-1);
  };

  // create return statement
  return (
    <PageLayout
      title="Braintree Integration"
      extra={<Button onClick={returnToDashboard}>Back to Integrations</Button>}
    >
      <div className="w-6/12">
        <h2 className="text-16px mb-10">
          Charge and invoice your customers through your Braintree account
        </h2>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-6 py-10">
          <h3>Import Braintree Customers:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => {
              const promise = importCustomersMutation.mutateAsync({
                source: "braintree",
              });
              toast.promise(promise, {
                pending: "Importing Customers From Braintree",
              });
            }}
          >
            Import
          </Button>
          {/* <h3 className="mx-0">Import Braintree Payments:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => {
              const promise = importPaymentsMutation.mutateAsync({
                source: "stripe",
              });
              toast.promise(promise, {
                pending: "Importing Past Payments From Braintree",
              });
            }}
          >
            Import
          </Button> */}
          {/* <h3>Transfer Subscriptions:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => {
              const promise = transferSubscriptionsMutation.mutateAsync({
                source: "stripe",
                end_now: false,
              });
              toast.promise(promise, {
                pending: "Transfering Subscriptions From Braintree",
              });
            }}
          >
            Transfer
          </Button> */}
          <h3>Create Lotus Customers In Braintree:</h3>
          <div className="flex h-6 items-center">
            <input
              id="comments"
              aria-describedby="comments-description"
              name="comments"
              type="checkbox"
              disabled={isSettingValue || !currentBraintreeSetting}
              checked={currentBraintreeSetting?.setting_values.value === true}
              onChange={(value) => {
                if (currentBraintreeSetting) {
                  updateBraintreeSettings.mutate({
                    setting_values: value.target.checked,
                    setting_id: currentBraintreeSetting.setting_id,
                  });
                }

                setIsSettingValue(true);
              }}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
          </div>
        </div>
        <div className="seperator" />
        <div />
      </div>
    </PageLayout>
  );
};

export default BraintreeIntegrationView;
