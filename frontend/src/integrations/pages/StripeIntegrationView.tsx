// @ts-ignore
import React, {FC, useEffect, useState} from "react";
import {useParams} from "react-router-dom";
import {useNavigate} from "react-router-dom";
import {PageLayout} from "../../components/base/PageLayout";
import {Button} from "antd";
import {useMutation, useQuery} from "react-query";
import {toast} from "react-toastify";
import {Stripe} from "../../api/api";
import {
    OrganizationSettings,
    Source,
    StripeImportCustomerResponse,
    TransferSub,
    UpdateOrganizationSettingsParams
} from "../../types/stripe-type";

const TOAST_POSITION =  toast.POSITION.TOP_CENTER;

//create FC component called StripeIntegration
const StripeIntegrationView: FC = () => {
    //create variable called {id} and set it to type string
    let {id} = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [isSettingValue, setIsSettingValue] = useState(false)
    const [currentOrganizationSetting, setCurrentOrganizationSetting] = useState<OrganizationSettings>();

    const getOrganizationSettings = async (): Promise<OrganizationSettings[]> => Stripe.getOrganizationSettings({setting_group: "stripe"});

    const {
        error,
        data,
        isLoading
    } = useQuery<OrganizationSettings[]>(["organization_settings"], getOrganizationSettings);


    useEffect(() => {
        if(!isLoading && !error && data) {
            setCurrentOrganizationSetting(data[0])
        }
    }, [isLoading, error, data])

    const importCustomersMutation = useMutation((post: Source) => Stripe.importCustomers(post),
        {
            onSuccess: (data: StripeImportCustomerResponse) => {
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

    const importPaymentsMutation = useMutation((post: Source) => Stripe.importPayments(post),
        {
            onSuccess: (data: StripeImportCustomerResponse) => {
                toast.success(data.detail, {
                    position: TOAST_POSITION,
                });
            },
            onError: () => {
                toast.error("Failed to Import Payments", {
                    position: TOAST_POSITION,
                });
            },
        }
    );

    const transferSubscriptionsMutation = useMutation((post: TransferSub) => Stripe.transferSubscriptions(post),
        {
            onSuccess: (data: StripeImportCustomerResponse) => {
                toast.success(data.detail, {
                    position: TOAST_POSITION,
                });
            },
            onError: () => {
                toast.error("Failed to transfer subscriptions", {
                    position: TOAST_POSITION,
                });
            },
        }
    );

    const updateOrganizationSettings = useMutation((post: UpdateOrganizationSettingsParams) => Stripe.updateOrganizationSettings(post),
        {
            onSuccess: (data: OrganizationSettings) => {
                setCurrentOrganizationSetting(data)
                setIsSettingValue(false)
                const state = data.setting_value === "true" ? "Enabled" : "Disabled"
                toast.success(`${state} the Organization Settings`, {
                    position: TOAST_POSITION,
                });
            },
            onError: () => {
                setIsSettingValue(false)
                toast.error("Failed to Update the organization settings", {
                    position: TOAST_POSITION,
                });
            },
        }
    );

    //create variable called returnToDashboard and set it to type void
    const returnToDashboard = () => {
        navigate(-1);
    };

    //create return statement
    return (
        <PageLayout
            title="Stripe Integration"
            extra={<button onClick={returnToDashboard}>Back to Integrations</button>}
        >
            <div className="w-6/12">
                <h2 className="text-16px mb-10">
                    Charge and invoice your customers through your Stripe account
                </h2>
                <div
                    className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-5 py-10">
                    <h3>Import Stripe Customers:</h3>
                    <Button size="large"
                            className="w-4/12"
                            onClick={() => importCustomersMutation.mutate({source: "stripe"})}
                    >
                        Import
                    </Button>
                    <h3 className="mx-0">Import Stripe Payments:</h3>
                    <Button
                        size="large"
                        className="w-4/12"
                        onClick={() => importPaymentsMutation.mutate({source: "stripe"})}
                    >
                        Import
                    </Button>
                    <h3>Transfer Subscriptions:</h3>
                    <Button size="large"
                            className="w-4/12"
                            onClick={() => transferSubscriptionsMutation.mutate({source: "stripe", end_now: true})}
                    >
                        Transfer
                    </Button>
                    <h3>Create Lotus Customers In Stripe:</h3>
                    <div className="flex h-5 items-center">
                        <input
                            id="comments"
                            aria-describedby="comments-description"
                            name="comments"
                            type="checkbox"
                            disabled={isSettingValue || !currentOrganizationSetting}
                            checked={currentOrganizationSetting?.setting_value === "true"}
                            onChange={value => {
                                updateOrganizationSettings.mutate(
                                    {
                                        setting_value: value.target.checked.toString(),
                                        setting_id:currentOrganizationSetting?.setting_id
                                    }
                                )
                                setIsSettingValue(true)
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                    </div>
                </div>
                <div className="seperator"/>
                <div/>
            </div>
        </PageLayout>
    );
};

export default StripeIntegrationView;
