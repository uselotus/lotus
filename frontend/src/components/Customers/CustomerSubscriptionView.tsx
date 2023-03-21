/* eslint-disable react/prop-types */
/* eslint-disable react/no-unstable-nested-components */
/* eslint-disable no-case-declarations */
/* eslint-disable no-shadow */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable no-nested-ternary */
/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
import moment from "moment";
import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import {
  Form,
  Button,
  InputNumber,
  Typography,
  Select,
  Modal,
  DatePicker,
  Input,
} from "antd";
import {
  RightOutlined,
  LeftOutlined,
  DoubleLeftOutlined,
} from "@ant-design/icons";
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseQueryResult,
} from "react-query";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { PlanType } from "../../types/plan-type";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionBody,
  CancelSubscriptionQueryParams,
  SubscriptionType,
  CreateSubscriptionAddOnBody,
} from "../../types/subscription-type";
import { integrationsMap } from "../../types/payment-processor-type";
// import the Customer type from the api.ts file

import DraftInvoice from "./DraftInvoice";
import CustomerCard from "./Card/CustomerCard";
import Divider from "../base/Divider/Divider";
import CopyText from "../base/CopytoClipboard";
import createShortenedText from "../../helpers/createShortenedText";
import useMediaQuery from "../../hooks/useWindowQuery";
import Badge from "../base/Badges/Badges";
import DropdownComponent from "../base/Dropdown/Dropdown";
import { AddOn, Customer, PaymentProcessor } from "../../api/api";
import { AddOnType } from "../../types/addon-type";

import ChevronDown from "../base/ChevronDown";
import CancelMenu from "./CancelMenu";
import SwitchMenu from "./SwitchMenu";
import CustomPagination from "../CustomPagination/CustomPagination";
import { components } from "../../gen-types";

interface Props {
  customer_id: string;
  subscriptions: components["schemas"]["CustomerDetail"]["subscriptions"];
  stripeSubscriptions: components["schemas"]["CustomerDetail"]["stripe_subscriptions"];
  upcomingSubscriptions: components["schemas"]["CustomerDetail"]["upcoming_subscriptions"];
  plans: PlanType[] | undefined;
  onAutoRenewOff: (
    subscription_id: string,
    props: components["schemas"]["SubscriptionRecordUpdateRequest"]
  ) => void;
  onCancel: (props: CancelSubscriptionBody, subscription_id: string) => void;
  onPlanChange: (
    params: components["schemas"]["SubscriptionRecordSwitchPlanRequest"],
    subscription_id: string
  ) => void;
  onCreate: (props: CreateSubscriptionType) => void;
}

interface ChangeOption {
  value:
    | "change_subscription_plan"
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
  label: string;
  disabled?: boolean;
}
interface PlanOption {
  value: string;
  label: string;
  children?: ChangeOption[];
  disabled?: boolean;
}

export interface CascaderOptions {
  value: string;
  plan_id: string;
  subscriptionFilters: SubscriptionType["subscription_filters"];
}

const dropDownOptions = [
  "Switch Plan",
  "Attach Add-On",
  "Cancel Renewal",
  "Cancel Now",
];

const subDropdownOptions = ["Cancel Now", "Cancel Renewal"];

const limit = 6;
const SubscriptionView: FC<Props> = ({
  customer_id,
  subscriptions,
  upcomingSubscriptions,
  stripeSubscriptions,
  plans,
  onCancel,
  onAutoRenewOff,
  onPlanChange,
  onCreate,
}) => {
  const [offset, setOffset] = useState(6);
  const [startingPoint, setStartingPoint] = useState(0);
  const [cursor, setCursor] = useState<string>("");
  const [rightCursor, setRightCursor] = useState<string>("");
  const [leftCursor, setLeftCursor] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [subStartDate, setSubStartDate] = useState<string>("");
  const [next, setNext] = useState<string>("");
  const [previous, setPrev] = useState<string>("");
  const [selectedSubPlan, setSelectedSubPlan] = useState<
    | components["schemas"]["CustomerDetail"]["subscriptions"][0]
    | components["schemas"]["CustomerDetail"]["stripe_subscriptions"][0]
    | undefined
  >();
  const [selectedPlan, setSelectedPlan] = useState<string>();

  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [addOnId, setAddOnId] = useState("");
  const [attachToPlanId, setAttachToPlanId] = useState("");
  const [attachToSubscriptionFilters, setAttachToSubscriptionFilters] =
    useState<SubscriptionType["subscription_filters"] | undefined>();
  const [quantity, setQuantity] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [title, setTitle] = useState("");
  const [cascaderOptions, setCascaderOptions] = useState<CascaderOptions>();
  const [cancelBody, setCancelBody] = useState<CancelSubscriptionBody>({
    usage_behavior: "bill_full",
    flat_fee_behavior: "charge_full",
    invoicing_behavior: "invoice_now",
  });
  const indexRef = useRef<
    "Switch Plan" | "Attach Add-On" | "Cancel Renewal" | "Cancel Now"
  >();
  const windowWidth = useMediaQuery();
  const [idtoPlan, setIDtoPlan] = useState<{ [key: string]: PlanType }>({});
  const [planList, setPlanList] =
    useState<{ label: string; value: string }[]>();

  const queryClient = useQueryClient();

  const selectPlan = (plan_id: string) => {
    setSelectedPlan(plan_id);
  };

  const { data: addOns, isLoading }: UseQueryResult<AddOnType[]> = useQuery<
    AddOnType[]
  >(["add-ons"], () => AddOn.getAddOns().then((res) => res), {
    refetchOnMount: "always",
  });

  const mutation = useMutation(
    (obj: {
      add_on: components["schemas"]["AddOnSubscriptionRecordCreateRequest"];
      subscription_id: string;
    }) => Customer.createSubscriptionAddOns(obj.add_on, obj.subscription_id),
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

  const cancelSubscription = (subscription_id: string) => {
    onCancel(cancelBody, subscription_id);
    setShowModal(false);
  };

  const cancelAllSubscriptions = () => {
    const query_params: CancelSubscriptionQueryParams = {
      customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_full",
      flat_fee_behavior: "charge_prorated",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
    setShowModal(false);
  };

  const cancelAndBill = (plan_id, subscription_filters) => {
    const query_params: CancelSubscriptionQueryParams = {
      plan_id,
      subscription_filters,
      customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_full",
      flat_fee_behavior: "charge_prorated",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
    setShowModal(false);
  };

  const turnAutoRenewOff = (subscription_id: string) => {
    onAutoRenewOff(subscription_id, {
      turn_off_auto_renew: true,
    });
    setShowModal(false);
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
          // for (let i = 0; i < plan.versions.length; i++) {
          //   if (
          //     plan.versions[i].status === "active" &&
          //     (plan.versions[i].target_customer.length === 0 ||
          //       plan.versions[i].target_customers.find(
          //         (cust) => cust.customer_id == customer_id
          //       ))
          //   ) {
          //     acc.push({
          //       label: plan.versions[i].plan_name,
          //       value: plan.plan_id,
          //     });
          //   }
          // }

          acc.push({ label: plan.plan_name, value: plan.plan_id });
          return acc;
        },
        [] as { label: string; value: string }[]
      );
      setPlanList(newplanList);
    }
  }, [customer_id, plans]);

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

  const onChange = (value: string, subscription_id: string) => {
    onPlanChange({ switch_plan_id: value as string }, subscription_id);
  };

  const handleAttachPlanSubmit = () => {
    if (selectedPlan) {
      const plan = idtoPlan[selectedPlan];
      const start_date = subStartDate ? subStartDate : new Date().toISOString();
      const props: CreateSubscriptionType = {
        customer_id,
        plan_id: plan.plan_id,
        start_date: start_date,
        auto_renew: true,
        is_new: true,
        subscription_filters: [],
        addons: [],
      };
      onCreate(props);
    }
    form.resetFields();
  };
  const submitAddOns = (subscription_id: string) => {
    const body = {
      add_on: { addon_id: addOnId, quantity },
      subscription_id,
    };

    mutation.mutate(body);
    setShowModal(false);
  };

  const getFilteredSubscriptions = useCallback(() => {
    if (!searchQuery) {
      return subscriptions;
    }
    return subscriptions.filter(
      (subscription) =>
        subscription.billing_plan.plan_id
          .toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        subscription.billing_plan.plan_name
          .toLowerCase()
          .includes(searchQuery.toLowerCase())
    );
  }, [subscriptions, searchQuery]);

  const getFilteredStripeSubscriptions = useCallback(() => {
    if (!searchQuery) {
      return stripeSubscriptions;
    }
    return stripeSubscriptions.filter(
      (stripeSubscriptions) =>
        stripeSubscriptions.billing_plan.plan_id
          .toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        stripeSubscriptions.billing_plan.plan_name
          .toLowerCase()
          .includes(searchQuery.toLowerCase())
    );
  }, [stripeSubscriptions, searchQuery]);

  const handleMovements = (direction: "LEFT" | "RIGHT" | "START") => {
    switch (direction) {
      case "LEFT":
        setCursor("NON-EMPTY");
        setCurrentPage(currentPage - 1);
        setRightCursor("");
        if (
          subscriptions.length % limit === 0 &&
          offset !== subscriptions.length
        ) {
          setStartingPoint((prevStartingPoint) => prevStartingPoint - limit);
          setOffset((prevOffset) => prevOffset - limit);
        } else {
          setOffset(startingPoint);
          setStartingPoint((prevStartingPoint) => prevStartingPoint - limit);
        }
        return;
      case "RIGHT":
        setLeftCursor("");
        setCursor("NON-EMPTY");
        if (offset <= subscriptions.length) {
          const newPage = currentPage + 1;
          setCurrentPage(newPage);
          setStartingPoint(offset);
          setOffset((prevOffset) => prevOffset + limit);
        } else {
          setOffset(subscriptions.length);
          setRightCursor("RIGHT-END");
        }
        break;
      case "START":
        setCursor("");
        setLeftCursor("LEFT-END");
        setCurrentPage(1);
        setOffset(6);
        setStartingPoint(0);
        if (offset > subscriptions.length) {
          setRightCursor("RIGHT-END");
        } else {
          setRightCursor("");
        }
        break;
      default:
        break;
    }
  };
  React.useLayoutEffect(() => {
    if (currentPage === 1) {
      handleMovements("START");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, subscriptions]);
  React.useLayoutEffect(() => {
    if (offset >= subscriptions.length) {
      setRightCursor("RIGHT-END");
    } else {
      setRightCursor("");
    }
  }, [offset, subscriptions]);
  if (
    subscriptions.length === 0 &&
    stripeSubscriptions.length === 0 &&
    upcomingSubscriptions.length === 0
  ) {
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
                value={selectedPlan}
              />
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

  function SubscriptionItem({
    subPlan,
    fromUpcoming,
  }: {
    subPlan: components["schemas"]["CustomerDetail"]["subscriptions"][0];
    fromUpcoming: boolean;
  }) {
    return (
      <div key={subPlan.billing_plan.plan_id + subPlan.subscription_filters}>
        <CustomerCard
          className={`shadow-none ${
            windowWidth > 2500 ? `h-[290px]` : "h-[270px]"
          } `}
          key={subPlan.billing_plan.plan_id + subPlan.subscription_filters}
        >
          <CustomerCard.Heading>
            <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
              <div>
                <div> {subPlan.billing_plan.plan_name}</div>
                {subPlan.subscription_filters ? (
                  subPlan.subscription_filters.length > 0 ? (
                    <p>
                      {subPlan.subscription_filters.map((filter) => (
                        <span key={filter.property_name}>
                          {filter.property_name}: {filter.value}
                        </span>
                      ))}
                    </p>
                  ) : null
                ) : null}
              </div>
            </Typography.Title>
            <Divider />
            <CustomerCard.Container>
              <CustomerCard.Block>
                <CustomerCard.Item>
                  <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
                    Subscription ID
                  </div>
                  <div className="flex gap-1 !text-card-grey font-menlo">
                    {" "}
                    <div>
                      {createShortenedText(
                        subPlan.subscription_id as string,
                        windowWidth >= 2500
                      )}
                    </div>
                    <CopyText
                      showIcon
                      onlyIcon
                      textToCopy={subPlan.subscription_id as string}
                    />
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Start Date
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {dayjs(subPlan.start_date).format("YYYY/MM/DD")}
                    </div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    End Date
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {dayjs(subPlan.end_date).format("YYYY/MM/DD")}
                    </div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Renews
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
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
              <div className="flex gap-4 items-center">
                <DropdownComponent>
                  <DropdownComponent.Trigger>
                    <button
                      type="button"
                      className="relative w-full min-w-[151px] flex items-center gap-4  cursor-default p-6 mt-4 bg-[#fff4e9] rounded-md border border-[#fff4e9]  py-2 pl-3 pr-10 text-left shadow-sm  focus:outline-none  sm:text-sm hover:text-black hover:bg-[#f8e8d7]"
                      aria-haspopup="listbox"
                      aria-expanded="true"
                      aria-labelledby="listbox-label"
                    >
                      <span className="block truncate">Plan Actions</span>
                      <ChevronDown />
                    </button>
                  </DropdownComponent.Trigger>
                  {!fromUpcoming ? (
                    <DropdownComponent.Container className="!bg-[#fff4e9] ">
                      {dropDownOptions.map((key, index) => (
                        <DropdownComponent.MenuItem
                          className="hover:text-black hover:bg-[#f8e8d7] whitespace-nowrap"
                          // eslint-disable-next-line react/no-array-index-key
                          key={index}
                          onSelect={() => {
                            setSelectedSubPlan(subPlan);
                            switch (index) {
                              case 0:
                                setTitle("Switch Plan");

                                setShowModal(true);
                                indexRef.current = "Switch Plan";
                                break;
                              case 1:
                                setTitle(
                                  `Attach Add-On to ${subPlan.billing_plan.plan_name}`
                                );

                                setShowModal(true);
                                indexRef.current = "Attach Add-On";
                                break;

                              case 2:
                                setTitle("Are you sure?");

                                setShowModal(true);
                                indexRef.current = "Cancel Renewal";
                                break;
                              default:
                                setTitle("Are you sure?");

                                setShowModal(true);
                                indexRef.current = "Cancel Now";
                            }
                          }}
                        >
                          {key}
                        </DropdownComponent.MenuItem>
                      ))}
                    </DropdownComponent.Container>
                  ) : (
                    // from upcoming
                    <DropdownComponent.Container className="!bg-[#fff4e9] ">
                      {subDropdownOptions.map((key, index) => (
                        <DropdownComponent.MenuItem
                          className="hover:text-black hover:bg-[#f8e8d7] whitespace-nowrap"
                          // eslint-disable-next-line react/no-array-index-key
                          key={index}
                          onSelect={() => {
                            setSelectedSubPlan(subPlan);
                            switch (index) {
                              case 0:
                                setTitle("Are you sure?");

                                setShowModal(true);
                                indexRef.current = "Cancel Now";
                                break;
                              default:
                                setTitle("Are you sure?");

                                setShowModal(true);
                                indexRef.current = "Cancel Renewal";
                                break;
                            }
                          }}
                        >
                          {key}
                        </DropdownComponent.MenuItem>
                      ))}
                    </DropdownComponent.Container>
                  )}
                </DropdownComponent>
                <div className=" flex-row flex font-alliance  items-center border-inherit w-full">
                  {subPlan.addons.map((addon) => (
                    <div
                      aria-hidden
                      onClick={() => {
                        navigate(`/add-ons/${addon.addon.addon_id}`);
                      }}
                      key={addon.addon.addon_id}
                      className="flex gap-2 items-center p-2 mt-4 bg-dark rounded-md border text-white border-[#fff4e9] py-2 pl-3 pr-10 text-left shadow-sm  focus:outline-none "
                    >
                      {addon.addon.addon_name}
                    </div>
                  ))}
                </div>
              </div>
            </CustomerCard.Container>
          </CustomerCard.Heading>
        </CustomerCard>

        {showModal ? (
          <Modal
            transitionName=""
            maskTransitionName=""
            className="font-alliance"
            title={title}
            visible={showModal}
            cancelButtonProps={{ hidden: true }}
            closeIcon={<div style={{ display: "none" }} className="hidden" />}
            onCancel={() => {
              setShowModal(false);
              setTitle("");
              setSelectedSubPlan(undefined);
            }}
            footer={
              indexRef.current === "Switch Plan"
                ? [
                    <Button key="back" onClick={() => setShowModal(false)}>
                      Cancel
                    </Button>,
                    <Button
                      key="switch_plan"
                      type="primary"
                      className="hover:!bg-primary-700 "
                      style={{
                        background: "#C3986B",
                        borderColor: "#C3986B",
                      }}
                      onClick={() => {
                        onChange(
                          cascaderOptions?.value as string,
                          subPlan.subscription_id
                        );
                        setShowModal(false);
                        setCascaderOptions(undefined);
                      }}
                    >
                      Switch
                    </Button>,
                  ]
                : indexRef.current === "Attach Add-On"
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
                      onClick={() => {
                        submitAddOns(selectedSubPlan!.subscription_id);
                      }}
                    >
                      Add
                    </Button>,
                  ]
                : indexRef.current === "Cancel Renewal"
                ? [
                    <Button key="back" onClick={() => setShowModal(false)}>
                      Back
                    </Button>,
                    <Button
                      key="submit"
                      type="primary"
                      className="!bg-rose-600 border !border-rose-600"
                      onClick={() => {
                        turnAutoRenewOff(selectedSubPlan!.subscription_id);
                      }}
                    >
                      Cancel Renewal
                    </Button>,
                  ]
                : indexRef.current === "Cancel Now"
                ? [
                    <Button key="back" onClick={() => setShowModal(false)}>
                      Back
                    </Button>,
                    <Button
                      key="submit"
                      type="primary"
                      className="!bg-rose-600 border !border-rose-600"
                      onClick={() => {
                        if (selectedSubPlan?.stripe_subscription_id) {
                          PaymentProcessor.cancelStripeSubscriptions({
                            customer_id:
                              selectedSubPlan?.customer.customer_id || "",
                            stripe_subscription_ids: [
                              selectedSubPlan.stripe_subscription_id,
                            ],
                          });
                          setShowModal(false);
                          queryClient.invalidateQueries([
                            "customer_detail",
                            customer_id,
                          ]);
                        } else {
                          cancelSubscription(selectedSubPlan!.subscription_id);
                        }
                      }}
                    >
                      Cancel Plan
                    </Button>,
                  ]
                : // : indexRef.current === 5
                  // ? [
                  //     <Button
                  //       key="back"
                  //       onClick={() => {
                  //         setShowModal(false);
                  //         setSubStartDate("");
                  //       }}
                  //     >
                  //       Back
                  //     </Button>,
                  //     <Button
                  //       key="submit"
                  //       type="primary"
                  //       className="hover:!bg-primary-700"
                  //       onClick={() => {
                  //         handleAttachPlanSubmit();
                  //         setShowModal(false);
                  //       }}
                  //     >
                  //       Start Subscription
                  //     </Button>,
                  //   ]
                  // : indexRef.current === 6
                  // ? [
                  //     <Button key="back" onClick={() => setShowModal(false)}>
                  //       Back
                  //     </Button>,
                  //     <Button
                  //       key="submit"
                  //       type="primary"
                  //       className="!bg-rose-600 border !border-rose-600"
                  //       onClick={() => {
                  //         cancelAllSubscriptions();
                  //       }}
                  //     >
                  //       Cancel All Subscriptions
                  //     </Button>,
                  //   ]
                  null
            }
          >
            <div className="flex flex-col justify-center items-center gap-4">
              {indexRef.current === "Switch Plan" ? (
                <SwitchMenu
                  plan_id={subPlan.billing_plan.plan_id}
                  subscription_filters={subPlan.subscription_filters}
                  subscriptions={subscriptions}
                  plansWithSwitchOptions={(plan_id) =>
                    plansWithSwitchOptions(plan_id)
                  }
                  setCascaderOptions={(args) => setCascaderOptions(args)}
                  cascaderOptions={cascaderOptions}
                />
              ) : indexRef.current ===
                "Cancel Renewal" ? null : indexRef.current === "Cancel Now" &&
                selectedSubPlan?.stripe_subscription_id ? null : indexRef.current ===
                "Cancel Now" ? (
                <CancelMenu
                  recurringBehavior={cancelBody.flat_fee_behavior}
                  usageBehavior={cancelBody.usage_behavior}
                  invoiceBehavior={cancelBody.invoicing_behavior}
                  setRecurringBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      flat_fee_behavior: e,
                    })
                  }
                  setUsageBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      usage_behavior: e,
                    })
                  }
                  setInvoiceBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      invoicing_behavior: e,
                    })
                  }
                />
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
                          const filters = subPlan.subscription_filters;

                          if (filters && filters.length > 0) {
                            setAttachToSubscriptionFilters(filters);
                          } else {
                            setAttachToSubscriptionFilters(undefined);
                          }
                        }}
                        style={{ width: "100%" }}
                        value={
                          addOns.find((addOn) => addOn.addon_id === addOnId)
                            ?.addon_name
                        }
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
        ) : null}
      </div>
    );
  }

  function StripeSubscriptionItem({
    sub,
  }: {
    sub: components["schemas"]["StripeSubscriptionRecord"];
  }) {
    // It's kinda trash ik, should def be defined as one SubscriptionItem
    return (
      <div key={sub.stripe_subscription_id}>
        <CustomerCard
          className={`shadow-none ${
            windowWidth > 2500 ? `h-[290px]` : "h-[270px]"
          } `}
          key={sub.stripe_subscription_id}
        >
          <CustomerCard.Heading>
            <div className="flex flex-row justify-between">
              <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
                <div>
                  <div>
                    Stripe Subscription ...
                    {sub.stripe_subscription_id.slice(-5)}
                  </div>
                  {sub.subscription_filters ? (
                    sub.subscription_filters.length > 0 ? (
                      <p>
                        {sub.subscription_filters.map((filter) => (
                          <span key={filter.property_name}>
                            {filter.property_name}: {filter.value}
                          </span>
                        ))}
                      </p>
                    ) : null
                  ) : null}
                </div>
              </Typography.Title>
              <img
                width={25}
                src={integrationsMap.stripe.icon}
                alt="payment provider logo"
              />
            </div>

            <Divider />
            <CustomerCard.Container>
              <CustomerCard.Block>
                <CustomerCard.Item>
                  <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
                    Subscription ID
                  </div>
                  <div className="flex gap-1 !text-card-grey font-menlo">
                    {" "}
                    <div>
                      {createShortenedText(
                        sub.stripe_subscription_id as string,
                        windowWidth >= 2500
                      )}
                    </div>
                    <CopyText
                      showIcon
                      onlyIcon
                      textToCopy={sub.stripe_subscription_id as string}
                    />
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Start Date
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {dayjs(sub.start_date).format("YYYY/MM/DD")}
                    </div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    End Date
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {dayjs(sub.end_date).format("YYYY/MM/DD")}
                    </div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Renews
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      <Badge
                        className={` ${
                          !sub.auto_renew
                            ? "bg-rose-700 text-white"
                            : "bg-emerald-100"
                        }`}
                      >
                        <Badge.Content>{String(sub.auto_renew)}</Badge.Content>
                      </Badge>
                    </div>
                  </div>
                </CustomerCard.Item>
              </CustomerCard.Block>
              <Divider />
              <div className="flex gap-4 items-center">
                <DropdownComponent>
                  <DropdownComponent.Trigger>
                    <button
                      type="button"
                      className="relative w-full min-w-[151px] flex items-center gap-4  cursor-default p-6 mt-4 bg-[#fff4e9] rounded-md border border-[#fff4e9]  py-2 pl-3 pr-10 text-left shadow-sm  focus:outline-none  sm:text-sm hover:text-black hover:bg-[#f8e8d7]"
                      aria-haspopup="listbox"
                      aria-expanded="true"
                      aria-labelledby="listbox-label"
                    >
                      <span className="block truncate">Plan Actions</span>
                      <ChevronDown />
                    </button>
                  </DropdownComponent.Trigger>
                  <DropdownComponent.Container className="!bg-[#fff4e9] ">
                    {subDropdownOptions.map((key, index) => (
                      <DropdownComponent.MenuItem
                        className="hover:text-black hover:bg-[#f8e8d7] whitespace-nowrap"
                        // eslint-disable-next-line react/no-array-index-key
                        key={index}
                        onSelect={() => {
                          setSelectedSubPlan(sub);
                          switch (index) {
                            case 0:
                              setTitle("Are you sure?");

                              setShowModal(true);
                              indexRef.current = "Cancel Now";
                              break;
                            default:
                              setTitle("Are you sure?");

                              setShowModal(true);
                              indexRef.current = "Cancel Renewal";
                              break;
                          }
                        }}
                      >
                        {key}
                      </DropdownComponent.MenuItem>
                    ))}
                  </DropdownComponent.Container>
                </DropdownComponent>
                <div className=" flex-row flex font-alliance  items-center border-inherit w-full">
                  {sub.addons.map((addon) => (
                    <div
                      aria-hidden
                      onClick={() => {
                        navigate(`/add-ons/${addon.addon.addon_id}`);
                      }}
                      key={addon.addon.addon_id}
                      className="flex gap-2 items-center p-2 mt-4 bg-dark rounded-md border text-white border-[#fff4e9] py-2 pl-3 pr-10 text-left shadow-sm  focus:outline-none "
                    >
                      {addon.addon.addon_name}
                    </div>
                  ))}
                </div>
              </div>
            </CustomerCard.Container>
          </CustomerCard.Heading>
        </CustomerCard>

        {showModal ? (
          <Modal
            transitionName=""
            maskTransitionName=""
            className="font-alliance"
            title={title}
            visible={showModal}
            cancelButtonProps={{ hidden: true }}
            closeIcon={<div style={{ display: "none" }} className="hidden" />}
            onCancel={() => {
              setShowModal(false);
              setTitle("");
              setSelectedSubPlan(undefined);
            }}
            footer={
              indexRef.current === "Cancel Now"
                ? [
                    <Button key="back" onClick={() => setShowModal(false)}>
                      Back
                    </Button>,
                    <Button
                      key="submit"
                      type="primary"
                      className="!bg-rose-600 border !border-rose-600"
                      onClick={() => {
                        if (selectedSubPlan?.stripe_subscription_id) {
                          PaymentProcessor.cancelStripeSubscriptions({
                            customer_id:
                              selectedSubPlan?.customer.customer_id || "",
                            stripe_subscription_ids: [
                              selectedSubPlan.stripe_subscription_id,
                            ],
                          });
                          setShowModal(false);
                          queryClient.invalidateQueries([
                            "customer_detail",
                            customer_id,
                          ]);
                        } else {
                          cancelSubscription(selectedSubPlan!.subscription_id);
                        }
                      }}
                    >
                      Cancel Plan
                    </Button>,
                  ]
                : [
                    <Button key="back" onClick={() => setShowModal(false)}>
                      Back
                    </Button>,
                    <Button
                      key="submit"
                      type="primary"
                      className="!bg-rose-600 border !border-rose-600"
                      onClick={() => {
                        if (selectedSubPlan?.stripe_subscription_id) {
                          PaymentProcessor.cancelAtPeriodEndStripeSubscriptions(
                            {
                              customer_id:
                                selectedSubPlan?.customer.customer_id || "",
                              stripe_subscription_ids: [
                                selectedSubPlan.stripe_subscription_id,
                              ],
                            }
                          );
                          setShowModal(false);
                          queryClient.invalidateQueries([
                            "customer_detail",
                            customer_id,
                          ]);
                        } else {
                          turnAutoRenewOff(selectedSubPlan!.subscription_id);
                        }
                      }}
                    >
                      Cancel Renewal
                    </Button>,
                  ]
            }
          >
            <div className="flex flex-col justify-center items-center gap-4">
              {indexRef.current === 0 ? (
                <SwitchMenu
                  plan_id={sub.billing_plan.plan_id}
                  subscription_filters={sub.subscription_filters}
                  subscriptions={subscriptions}
                  plansWithSwitchOptions={(plan_id) =>
                    plansWithSwitchOptions(plan_id)
                  }
                  setCascaderOptions={(args) => setCascaderOptions(args)}
                  cascaderOptions={cascaderOptions}
                />
              ) : indexRef.current ===
                "Cancel Renewal" ? null : indexRef.current === "Cancel Now" &&
                selectedSubPlan?.stripe_subscription_id ? null : indexRef.current ===
                "Cancel Now" ? (
                <CancelMenu
                  recurringBehavior={cancelBody.flat_fee_behavior}
                  usageBehavior={cancelBody.usage_behavior}
                  invoiceBehavior={cancelBody.invoicing_behavior}
                  setRecurringBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      flat_fee_behavior: e,
                    })
                  }
                  setUsageBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      usage_behavior: e,
                    })
                  }
                  setInvoiceBehavior={(e) =>
                    setCancelBody({
                      ...cancelBody,
                      invoicing_behavior: e,
                    })
                  }
                />
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
                          setAttachToPlanId(sub.billing_plan.plan_id);
                          setAddOnId(e);
                          const filters = sub.subscription_filters;

                          if (filters && filters.length > 0) {
                            setAttachToSubscriptionFilters(filters);
                          } else {
                            setAttachToSubscriptionFilters(undefined);
                          }
                        }}
                        style={{ width: "100%" }}
                        value={
                          addOns.find((addOn) => addOn.addon_id === addOnId)
                            ?.addon_name
                        }
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
        ) : null}
      </div>
    );
  }

  function RenderSubscriptions({
    searchQuery,
    subscriptions,
    stripeSubscriptions,
    startingPoint,
    offset,
  }: {
    searchQuery: string;
    subscriptions: components["schemas"]["CustomerDetail"]["subscriptions"];
    startingPoint: number;
    offset: number;
  }) {
    const subscriptionList = searchQuery
      ? getFilteredSubscriptions().map((subPlan) => (
          <SubscriptionItem
            fromUpcoming={false}
            key={subPlan.billing_plan.plan_id + subPlan.subscription_filters}
            subPlan={subPlan}
          />
        ))
      : subscriptions
          .slice(startingPoint, offset)
          .map((subPlan) => (
            <SubscriptionItem
              fromUpcoming={false}
              key={subPlan.billing_plan.plan_id + subPlan.subscription_filters}
              subPlan={subPlan}
            />
          ));

    const stripeSubscriptionList = searchQuery
      ? getFilteredStripeSubscriptions().map((subPlan) => (
          <StripeSubscriptionItem
            key={subPlan.billing_plan.plan_id + subPlan.subscription_filters}
            sub={subPlan}
          />
        ))
      : stripeSubscriptions
          .slice(startingPoint, offset)
          .map((subPlan) => (
            <StripeSubscriptionItem
              key={subPlan.subscription_id}
              sub={subPlan}
            />
          ));

    return (
      <div className="grid gap-20 min-h-[564px]  grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        <>{stripeSubscriptionList}</>
        <>{subscriptionList}</>
      </div>
    );
  }

  console.log(subscriptions, upcomingSubscriptions);

  return (
    <div className="mt-auto">
      <div className="flex mb-2 pb-4 pt-4 items-center justify-center">
        <h2 className="font-bold text-main">Active Subscriptions</h2>
        <div className="ml-auto flex gap-2 max-h-[40px]">
          <Input
            placeholder="Search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {/* <Button
            type="primary"
            className="hover:!bg-rose-700"
            size="large"
            disabled={false}
            onClick={() => {
              indexRef.current = 6;
              setTitle("Cancel All Subscriptions");

              setShowModal(true);
            }}
          >
            Cancel All
          </Button> */}
          <Button
            type="primary"
            className="hover:!bg-primary-700"
            style={{ background: "#C3986B", borderColor: "#C3986B" }}
            size="large"
            disabled={false}
            onClick={() => {
              setTitle("Add New Plan");

              setShowAddModal(true);
            }}
          >
            Add New Plan
          </Button>
        </div>
      </div>
      <div className="flex flex-col justify-center">
        <RenderSubscriptions
          searchQuery={searchQuery}
          subscriptions={subscriptions}
          stripeSubscriptions={stripeSubscriptions}
          startingPoint={startingPoint}
          offset={offset}
        />
        <div className="mt-4">
          <div className="flex justify-center space-x-4">
            <button
              type="button"
              disabled={!cursor || currentPage === 1}
              className="movementButton"
              onClick={() => handleMovements("START")}
            >
              <DoubleLeftOutlined />
            </button>
            <button
              type="button"
              className="movementButton"
              disabled={leftCursor === "LEFT-END"}
              onClick={() => handleMovements("LEFT")}
            >
              <LeftOutlined />
            </button>
            <div className="currentPageNumber"> {currentPage} </div>
            <button
              type="button"
              className="movementButton"
              disabled={rightCursor === "RIGHT-END"}
              onClick={() => handleMovements("RIGHT")}
            >
              <RightOutlined />
            </button>
          </div>
        </div>
      </div>
      {upcomingSubscriptions.length > 0 && (
        <>
          <div className="flex mb-2 pb-4 pt-4 items-center justify-start">
            <h2 className="font-bold text-main">Upcoming Subscriptions</h2>
          </div>
          <div className="flex flex-col justify-center">
            <div className="grid gap-20 min-h-[564px]  grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
              {upcomingSubscriptions.map((sub) => (
                <SubscriptionItem
                  key={sub.subscription_id}
                  fromUpcoming
                  subPlan={sub}
                />
              ))}
            </div>
          </div>
        </>
      )}
      {showAddModal ? (
        <Modal
          transitionName=""
          maskTransitionName=""
          className="font-alliance"
          title={title}
          visible={showAddModal}
          cancelButtonProps={{ hidden: true }}
          closeIcon={<div style={{ display: "none" }} className="hidden" />}
          onCancel={() => {
            setShowAddModal(false);
            setTitle("");
            setSelectedSubPlan(undefined);
          }}
          footer={[
            <Button
              key="back"
              onClick={() => {
                setShowAddModal(false);
                setSubStartDate("");
              }}
            >
              Back
            </Button>,
            <Button
              key="submit"
              type="primary"
              className="hover:!bg-primary-700"
              onClick={() => {
                handleAttachPlanSubmit();
                setShowAddModal(false);
              }}
            >
              Start Subscription
            </Button>,
          ]}
        >
          <div className="flex flex-col gap-2">
            <Select
              showSearch
              placeholder="Select a plan"
              onChange={selectPlan}
              options={planList}
              value={selectedPlan}
              optionLabelProp="label"
            ></Select>

            <DatePicker
              showTime
              className="mt-0"
              placeholder="Select start date"
              onChange={(date, dateString) => setSubStartDate(dateString)}
              value={subStartDate ? moment(subStartDate) : undefined}
            />
          </div>
        </Modal>
      ) : null}
      <DraftInvoice customer_id={customer_id} />
    </div>
  );
};

export default SubscriptionView;
