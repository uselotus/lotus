import React, { FC, useEffect, useRef, useState } from "react";
import { PlanType } from "../../types/plan-type";
import {
  Form,
  Button,
  Menu,
  InputNumber,
  Cascader,
  Typography,
  Select,
  Modal,
} from "antd";
import type { DefaultOptionType } from "antd/es/cascader";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionBody,
  CancelSubscriptionQueryParams,
  SubscriptionType,
  CreateSubscriptionAddOnBody,
} from "../../types/subscription-type";
//import the Customer type from the api.ts file

import DraftInvoice from "./DraftInvoice";
import CustomerCard from "./Card/CustomerCard";
import Divider from "../base/Divider/Divider";
import CopyText from "../base/CopytoClipboard";
import createShortenedText from "../../helpers/createShortenedText";
import useMediaQuery from "../../hooks/useWindowQuery";
import Badge from "../base/Badges/Badges";
import DropdownComponent from "../base/Dropdown/Dropdown";
import { DraftInvoiceType } from "../../types/invoice-type";
import { Addon, Customer, Invoices } from "../../api/api";
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseQueryResult,
} from "react-query";
import { AddonType } from "../../types/addon-type";
import { toast } from "react-toastify";
interface Props {
  customer_id: string;
  subscriptions: SubscriptionType[];
  plans: PlanType[] | undefined;
  onAutoRenewOff: (
    params: object,
    props: TurnSubscriptionAutoRenewOffType
  ) => void;
  onCancel: (
    props: CancelSubscriptionBody,
    params: CancelSubscriptionQueryParams
  ) => void;
  onPlanChange: (params: object, props: ChangeSubscriptionPlanType) => void;
  onCreate: (props: CreateSubscriptionType) => void;
}

const filter = (inputValue: string, path: DefaultOptionType[]) =>
  (path[0].label as string).toLowerCase().indexOf(inputValue.toLowerCase()) >
  -1;

const displayRender = (labels: string[]) => labels[labels.length - 1];

interface PlanOption {
  value: string;
  label: string;
  children?: ChangeOption[];
  disabled?: boolean;
}

interface ChangeOption {
  value:
    | "change_subscription_plan"
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
  label: string;
  disabled?: boolean;
}

const SubscriptionView: FC<Props> = ({
  customer_id,
  subscriptions,
  plans,
  onCancel,
  onAutoRenewOff,
  onPlanChange,
  onCreate,
}) => {
  const [selectedPlan, setSelectedPlan] = useState<string>();
  const [form] = Form.useForm();
  const [addOnId, setAddOnId] = useState("");
  const [attachToPlanId, setAttachToPlanId] = useState("");
  const [attachToSubscriptionFilters, setAttachToSubscriptionFilters] =
    useState<SubscriptionType["subscription_filters"] | undefined>();
  const [quantity, setQuantity] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState("");
  const [cancelSubType, setCancelSubType] = useState<
    "bill_now" | "remove_renewal"
  >("bill_now");
  const indexRef = useRef(0);
  const windowWidth = useMediaQuery();
  const [idtoPlan, setIDtoPlan] = useState<{ [key: string]: PlanType }>({});
  const [planList, setPlanList] =
    useState<{ label: string; value: string }[]>();
  const dropDownOptions = [
    "Switch Plan",
    "Attach Add-On",
    "Cancel Subscription",
  ];
  const subscriptionCancellationOptions = [
    { name: "Cancel and Bill  Now", type: "bill_now" },
    { name: "Cancel Renewal", type: "remove_renewal" },
  ];
  const queryClient = useQueryClient();

  const selectPlan = (plan_id: string) => {
    setSelectedPlan(plan_id);
  };
  const { data: invoiceData } = useQuery<DraftInvoiceType>(
    ["draft_invoice", customer_id],
    () => Invoices.getDraftInvoice(customer_id),
    {
      refetchOnMount: "always",
    }
  );
  const { data: addOns, isLoading }: UseQueryResult<AddonType[]> = useQuery<
    AddonType[]
  >(
    ["add-ons"],
    () =>
      Addon.getAddons().then((res) => {
        return res;
      }),
    {
      refetchOnMount: "always",
    }
  );
  const mutation = useMutation(
    (add_on: CreateSubscriptionAddOnBody) =>
      Customer.createSubscriptionAddOns(add_on),
    {
      onSuccess: () => {
        toast.success("Successfully Created Subscription Add-on", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["add-ons"]);
        queryClient.invalidateQueries(["customer_detail", customer_id]);
        queryClient.invalidateQueries(["draft_invoice", customer_id]);
      },
      onError: () => {
        toast.error("Failed to create Subscription Add-on", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );
  const cancelAndBill = (plan_id, subscription_filters) => {
    const query_params: CancelSubscriptionQueryParams = {
      plan_id: plan_id,
      subscription_filters: subscription_filters,
      customer_id: customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_full",
      flat_fee_behavior: "prorate",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
  };

  const cancelAndDontBill = (plan_id, subscription_filters) => {
    const query_params: CancelSubscriptionQueryParams = {
      plan_id: plan_id,
      subscription_filters: subscription_filters,
      customer_id: customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_none",
      flat_fee_behavior: "prorate",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
  };

  const turnAutoRenewOff = (plan_id, subscription_filters) => {
    onAutoRenewOff(
      {
        plan_id: plan_id,
        subscription_filters: subscription_filters,
        customer_id: customer_id,
      },
      {
        turn_off_auto_renew: true,
      }
    );
  };

  useEffect(() => {
    if (plans !== undefined) {
      const planMap = plans.reduce((acc, plan) => {
        acc[plan.plan_id] = plan;
        return acc;
      }, {} as { [key: number]: PlanType });
      setIDtoPlan(planMap);
      const newplanList: { label: string; value: string }[] = plans.reduce(
        (acc, plan) => {
          if (
            plan.target_customer === null ||
            plan.target_customer?.customer_id === customer_id
          ) {
            acc.push({ label: plan.plan_name, value: plan.plan_id });
          }
          return acc;
        },
        [] as { label: string; value: string }[]
      );
      setPlanList(newplanList);
    }
  }, [plans]);

  const cancelMenu = (plan_id: string, subscription_filters?: object[]) => (
    <div className="flex gap-4">
      {subscriptionCancellationOptions.map((options) => (
        <div key={options.type} className="flex items-center gap-2">
          <input
            id={options.type}
            name="subscription cancel"
            type="radio"
            onChange={(e) =>
              setCancelSubType(e.target.value as typeof cancelSubType)
            }
            defaultChecked={options.type === "bill_now"}
            className="h-8 w-8 border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          <label
            htmlFor={options.type}
            className="ml-3 block text-sm font-medium text-gray-700"
          >
            {options.name}
          </label>
        </div>
      ))}
    </div>
  );
  // <Menu
  //   items={[
  //     {
  //       label: (
  //         <div onClick={() => cancelAndBill(plan_id, subscription_filters)}>
  //           Cancel and Bill Now
  //         </div>
  //       ),
  //       key: "0",
  //     },
  //     // {
  //     //   label: (
  //     //     <div
  //     //       onClick={() => cancelAndDontBill(plan_id, subscription_filters)}
  //     //     >
  //     //       Cancel Without Billing & Refund
  //     //     </div>
  //     //   ),
  //     //   key: "1",
  //     // },
  //     {
  //       label: (
  //         <div
  //           aria-hidden
  //           onClick={() => turnAutoRenewOff(plan_id, subscription_filters)}
  //         >
  //           Cancel Renewal
  //         </div>
  //       ),
  //       key: "2",
  //     },
  //   ]}
  // />

  const plansWithSwitchOptions = (plan_id: string) =>
    planList?.reduce((acc, plan) => {
      if (plan.value !== plan_id) {
        acc.push({
          label: plan.label,
          value: plan.value,
        } as PlanOption);
      }
      return acc;
    }, [] as PlanOption[]);

  const onChange = (
    value: any,
    selectedOptions: PlanOption[],
    plan_id: string,
    subscription_filters: object[]
  ) => {
    onPlanChange(
      {
        plan_id: plan_id,
        customer_id: customer_id,
        subscription_filters: subscription_filters,
      },
      {
        replace_plan_id: selectedOptions[0].value as string,
      }
    );
  };

  const switchMenu = (plan_id: string, subscription_filters: object[]) => (
    <Cascader
      options={plansWithSwitchOptions(plan_id)}
      onChange={(value, selectedOptions) =>
        onChange(value, selectedOptions, plan_id, subscription_filters)
      }
      expandTrigger="hover"
      placeholder="Please select"
      showSearch={{ filter }}
      displayRender={displayRender}
      changeOnSelect
    />
  );

  const handleAttachPlanSubmit = () => {
    if (selectedPlan) {
      const plan = idtoPlan[selectedPlan];
      const props: CreateSubscriptionType = {
        customer_id: customer_id,
        plan_id: plan.plan_id,
        start_date: new Date().toISOString(),
        auto_renew: true,
        is_new: true,
        subscription_filters: [],
      };
      onCreate(props);
    }
    form.resetFields();
  };
  const submitAddOns = () => {
    const body = {
      attach_to_customer_id: customer_id,
      attach_to_plan_id: attachToPlanId,
      attach_to_subscription_filters: attachToSubscriptionFilters
        ? attachToSubscriptionFilters
        : [],
      addon_id: addOnId,
      quantity,
    };

    mutation.mutate(body);
    setShowModal(false);
  };
  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center">
        <h2 className="mb-2 pb-4 pt-4 font-bold text-main">No Subscription</h2>
        <p className="font-bold">Please attach a Plan</p>
        <div className=" h-3/6">
          <Form
            onFinish={handleAttachPlanSubmit}
            form={form}
            name="create_subscription"
          >
            <Form.Item name="plan">
              <Select
                showSearch
                placeholder="Select a plan"
                onChange={selectPlan}
                options={planList}
                optionLabelProp="label"
              >
                {" "}
              </Select>
            </Form.Item>
            <Form.Item>
              <Button htmlType="submit">
                {" "}
                Attach Plan and Start Subscription
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    );
  }

  const subFilters = (index: number) => {
    if (
      invoiceData &&
      invoiceData.invoices &&
      invoiceData.invoices.length > 0
    ) {
      return invoiceData?.invoices[0].line_items[index].subscription_filters;
    } else {
      return undefined;
    }
  };

  return (
    <div className="mt-auto">
      <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Active Plans</h2>
      <div className="flex flex-col justify-center">
        <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
          {subscriptions.map((subPlan, index) => (
            <>
              <CustomerCard key={subPlan.end_date}>
                <CustomerCard.Heading>
                  <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
                    <div>
                      <div> {subPlan.billing_plan.plan_name}</div>
                      {subFilters(index)?.length > 0 && (
                        <p>
                          {subFilters(index)!.map((filter) => {
                            return (
                              <span key={filter.property_name}>
                                {filter.property_name} : {filter.value}
                              </span>
                            );
                          })}
                        </p>
                      )}
                    </div>
                  </Typography.Title>
                  <Divider />
                  <CustomerCard.Container>
                    <CustomerCard.Block>
                      <CustomerCard.Item>
                        <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
                          ID
                        </div>
                        <div className="flex gap-1 !text-card-grey font-menlo">
                          {" "}
                          <div>
                            {createShortenedText(
                              subPlan.billing_plan.plan_id as string,
                              windowWidth >= 2500
                            )}
                          </div>
                          <CopyText
                            showIcon
                            onlyIcon
                            textToCopy={subPlan.billing_plan.plan_id as string}
                          />
                        </div>
                      </CustomerCard.Item>
                      <CustomerCard.Item>
                        <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                          Start Date
                        </div>
                        <div className="flex gap-1">
                          {" "}
                          <div className="Inter">{subPlan.start_date}</div>
                        </div>
                      </CustomerCard.Item>
                      <CustomerCard.Item>
                        <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                          End Date
                        </div>
                        <div className="flex gap-1">
                          {" "}
                          <div className="Inter">{subPlan.end_date}</div>
                        </div>
                      </CustomerCard.Item>
                      <CustomerCard.Item>
                        <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                          Renews
                        </div>
                        <div className="flex gap-1">
                          {" "}
                          <div className={`Inter`}>
                            <Badge
                              className={` ${
                                !subPlan.auto_renew
                                  ? "bg-rose-700 text-white"
                                  : "bg-emerald-100"
                              }`}
                            >
                              <Badge.Content>
                                {String(subPlan.auto_renew)}
                              </Badge.Content>
                            </Badge>
                          </div>
                        </div>
                      </CustomerCard.Item>
                    </CustomerCard.Block>
                    <Divider />
                    <DropdownComponent>
                      <DropdownComponent.Trigger>
                        <button
                          type="button"
                          className="relative w-full min-w-[151px] flex items-center gap-4  cursor-default p-6 mt-4 bg-[#fff4e9] rounded-md border border-[#fff4e9]  py-2 pl-3 pr-10 text-left shadow-sm  focus:outline-none  sm:text-sm"
                          aria-haspopup="listbox"
                          aria-expanded="true"
                          aria-labelledby="listbox-label"
                        >
                          <span className="block truncate">Plan Actions</span>
                          <svg
                            className="h-8"
                            aria-hidden="true"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            viewBox="0 0 24 24"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <path
                              d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            ></path>
                          </svg>
                        </button>
                      </DropdownComponent.Trigger>
                      <DropdownComponent.Container className="!bg-[#fff4e9]">
                        {dropDownOptions.map((key, index) => (
                          <DropdownComponent.MenuItem
                            className="hover:text-black whitespace-nowrap"
                            key={index}
                            onSelect={() => {
                              switch (index) {
                                case 0:
                                  indexRef.current = index;
                                  setTitle("Switch Plan");

                                  setShowModal(true);
                                  break;
                                case 1:
                                  indexRef.current = index;
                                  setTitle(
                                    `Attach Add-On to ${subPlan.billing_plan.plan_name}`
                                  );

                                  setShowModal(true);
                                  break;
                                default:
                                  indexRef.current = index;
                                  setTitle("Cancel Subscription");

                                  setShowModal(true);
                              }
                            }}
                          >
                            {key}
                          </DropdownComponent.MenuItem>
                        ))}
                      </DropdownComponent.Container>
                    </DropdownComponent>
                  </CustomerCard.Container>
                </CustomerCard.Heading>
              </CustomerCard>
              <Modal
                title={title}
                visible={showModal}
                cancelButtonProps={{ hidden: true }}
                closeIcon={
                  <div style={{ display: "none" }} className="hidden" />
                }
                onCancel={() => setShowModal(false)}
                footer={
                  indexRef.current === 0
                    ? [
                        <Button key="back" onClick={() => setShowModal(false)}>
                          Cancel
                        </Button>,
                      ]
                    : indexRef.current === 1
                    ? [
                        <Button key="back" onClick={() => setShowModal(false)}>
                          Cancel
                        </Button>,

                        <Button
                          key="submit"
                          type="primary"
                          className="hover:!bg-primary-700"
                          style={{
                            background: "#C3986B",
                            borderColor: "#C3986B",
                          }}
                          disabled={addOnId.length < 1}
                          onClick={submitAddOns}
                        >
                          Add
                        </Button>,
                      ]
                    : [
                        <Button key="back" onClick={() => setShowModal(false)}>
                          Exit
                        </Button>,
                        <Button
                          key="submit"
                          type="primary"
                          className="!bg-rose-600 border !border-rose-600"
                          onClick={() => {
                            cancelSubType === "bill_now"
                              ? cancelAndDontBill(
                                  subPlan.billing_plan.plan_id,
                                  subPlan.subscription_filters
                                )
                              : turnAutoRenewOff(
                                  subPlan.billing_plan.plan_id,
                                  subPlan.subscription_filters
                                );
                          }}
                        >
                          Cancel
                        </Button>,
                      ]
                }
              >
                <div className="flex flex-col justify-center items-center gap-4">
                  {indexRef.current === 0 ? (
                    switchMenu(
                      subPlan.billing_plan.plan_id,
                      subPlan.subscription_filters
                    )
                  ) : indexRef.current === 2 ? (
                    cancelMenu(
                      subPlan.billing_plan.plan_id,
                      subPlan.subscription_filters
                    )
                  ) : (
                    <Form.Provider>
                      <Form form={form} name="create_subscriptions_addons">
                        <Form.Item name="addon_id">
                          <label htmlFor="addon_id" className="mb-4 required">
                            Select Add-On
                          </label>
                          <Select
                            id="addon_id"
                            placeholder="Select An Option"
                            onChange={(e) => {
                              setAttachToPlanId(subPlan.billing_plan.plan_id);
                              setAddOnId(e);
                              const filters = subFilters(index);

                              if (filters && filters.length > 0) {
                                setAttachToSubscriptionFilters(filters);
                              } else {
                                setAttachToSubscriptionFilters(undefined);
                              }
                            }}
                            style={{ width: "100%" }}
                          >
                            {addOns && !isLoading
                              ? addOns.map((addOn) => (
                                  <Select.Option
                                    key={addOn.addon_id}
                                    value={addOn.addon_id}
                                  >
                                    {addOn.addon_name}
                                  </Select.Option>
                                ))
                              : null}
                          </Select>
                        </Form.Item>
                        <Form.Item name="quantity">
                          <label htmlFor="quantity" className="mb-4">
                            Quantity
                          </label>
                          <InputNumber
                            id="quantity"
                            style={{ width: "100%" }}
                            type="number"
                            onChange={(e) => {
                              setQuantity(e!);
                            }}
                            defaultValue={1}
                            controls
                          />
                        </Form.Item>
                      </Form>
                    </Form.Provider>
                  )}
                </div>
              </Modal>
            </>
          ))}
          {/* {subscriptions.map((subPlan) => (
            <Fragment key={subPlan.billing_plan.plan_id}>
              <List.Item>
                <Card className=" bg-grey3 w-full">
                  <div className="grid grid-cols-2 items-stretch">
                    <div>
                      <Link to={"../plans/" + subPlan.billing_plan.plan_id}>
                        {" "}
                        <h2 className="font-main font-bold hover:underline">
                          {subPlan.billing_plan.plan_name}
                        </h2>
                      </Link>
                      <b>Subscription Filters: </b>{" "}
                      {subPlan.subscription_filters &&
                      subPlan.subscription_filters.length > 0
                        ? subPlan.subscription_filters?.map((filter) => (
                            <div>
                              {filter["property_name"]}: {filter["value"]}
                            </div>
                          ))
                        : "None"}
                    </div>

                    <div className="grid grid-cols-2 justify-center space-y-3">
                      <p className=""></p>
                      <p>
                        <b>Start Date:</b>{" "}
                        {dayjs(subPlan.start_date).format("YYYY/MM/DD HH:mm")}{" "}
                      </p>

                      <p>
                        <b>Renews:</b>{" "}
                        {subPlan.auto_renew ? (
                          <Tag color="green">Yes</Tag>
                        ) : (
                          <Tag color="red">No</Tag>
                        )}
                      </p>
                      <p>
                        <b>End Date:</b>{" "}
                        {dayjs(subPlan.end_date).format("YYYY/MM/DD HH:mm")}{" "}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 w-full space-x-5 mt-12">
                    <Dropdown
                      overlay={switchMenu(
                        subPlan.billing_plan.plan_id,
                        subPlan.subscription_filters
                      )}
                      trigger={["click"]}
                      className="w-6/12 justify-self-center"
                    >
                      <Button>Switch Plan</Button>
                    </Dropdown>
                    <Dropdown
                      overlay={cancelMenu(
                        subPlan.billing_plan.plan_id,
                        subPlan.subscription_filters
                      )}
                      trigger={["click"]}
                      className="w-6/12 justify-self-center"
                    >
                      <Button>Cancel Subscriptions</Button>
                    </Dropdown>
                  </div>
                </Card>
              </List.Item>
            </Fragment>
          ))} */}
        </div>

        <DraftInvoice customer_id={customer_id} />
      </div>
    </div>
  );
};

export default SubscriptionView;
