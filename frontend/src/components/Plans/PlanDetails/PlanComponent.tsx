/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable camelcase */
// @ts-ignore
import React, { FC, useEffect, useRef, useState } from "react";
import "./PlanDetails.css";
import {
  Table,
  Typography,
  Menu,
  Modal,
  Input,
  Button,
  InputNumber,
  Dropdown,
  Divider,
} from "antd";
import {
  CheckCircleOutlined,
  EllipsisOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";
import StateTabs from "./StateTabs";
import {
  Component,
  PlanDetailType,
  PlanType,
  PlanVersionType,
  Tier,
} from "../../../types/plan-type";
import { CurrencyType } from "../../../types/pricing-unit-type";
import createShortenedText from "../../../helpers/createShortenedText";
import DropdownComponent from "../../base/Dropdown/Dropdown";
import PlansTags from "../PlanTags";
import LinkExternalIds from "../LinkExternalIds";
import capitalize from "../../../helpers/capitalize";
import CopyText from "../../base/CopytoClipboard";
import useVersionStore from "../../../stores/useVersionStore";
import Badge from "../../base/Badges/Badges";
import Select from "../../base/Select/Select";
import useMediaQuery from "../../../hooks/useWindowQuery";
import createTags from "../helpers/createTags";
import useGlobalStore from "../../../stores/useGlobalstore";
import createPlanTagsList from "../helpers/createPlanTagsList";
import { AlertType, CreateAlertType } from "../../../types/alert-type";
import { Plan } from "../../../api/api";

interface PlanComponentsProps {
  components?: Component[];
  plan: PlanType;
  refetch: VoidFunction;
  updateBillingFrequencyMutation: (
    billing_frequency: "monthly" | "quarterly" | "yearly"
  ) => void;
  alerts?: AlertType[];
  plan_version_id: string;
}

const findAlertForComponent = (
  component: Component,
  alerts: AlertType[] | undefined
): AlertType | undefined => {
  if (alerts === undefined) {
    return undefined;
  }
  return alerts.find(
    (alert) => alert.metric.metric_id === component.billable_metric.metric_id
  );
};

const renderCost = (record: Tier, pricing_unit: CurrencyType) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
        </span>
      );

    case "flat":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch}{" "}
        </span>
      );

    case "free":
      return <span>Free</span>;
  }
};
interface PlanSummaryProps {
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
  plan: PlanDetailType;
  createTagMutation: (variables: {
    plan_id: string;
    tags: PlanType["tags"];
  }) => void;
}
export function PlanSummary({
  plan,
  createTagMutation,
  createPlanExternalLink,
  deletePlanExternalLink,
}: PlanSummaryProps) {
  const { plan_tags } = useGlobalStore((state) => state.org);
  const windowWidth = useMediaQuery();
  const inputRef = useRef<HTMLInputElement | null>(null!);
  const [showEditTaxJarModal, setShowEditTaxJarModal] = useState(false);
  const [updatedTaxJarCode, setUpdatedTaxJarCode] = useState(plan.taxjar_code);
  const [currentTaxJarCode, setCurrentTaxJarCode] = useState(plan.taxjar_code);

  const updateTaxJarMutation = useMutation(
    () =>
      Plan.updatePlan(plan.plan_id, {
        taxjar_code: updatedTaxJarCode,
      }),
    {
      onSuccess: () => {
        toast.success("TaxJar Code Updated");
        setShowEditTaxJarModal(false);
        setCurrentTaxJarCode(updatedTaxJarCode);
      },
      onError: () => {
        toast.error("Error Updating TaxJar Code");
        setUpdatedTaxJarCode(currentTaxJarCode);
      },
    }
  );

  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-alliance rounded-sm bg-card">
      <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px] level={2}">
        Summary (All Versions)
      </Typography.Title>

      <div>
        <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className=" font-normal whitespace-nowrap leading-4">
            Plan ID
          </div>
          <div className="flex gap-1">
            {" "}
            <div className="!text-card-grey">
              {createShortenedText(plan.plan_id, windowWidth >= 2500)}
            </div>
            <CopyText showIcon onlyIcon textToCopy={plan.plan_id} />
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Total Active Subscriptions
          </div>
          <div className="!text-card-grey">{plan.active_subscriptions}</div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-2">
          <div className="font-normal whitespace-nowrap leading-4">
            <a
              href="https://developers.taxjar.com/api/reference/#get-list-tax-categories"
              target="_blank"
              rel="noopener noreferrer"
            >
              TaxJar Code
            </a>
          </div>
          <div>
            {currentTaxJarCode ? (
              <div className="flex gap-1">
                {" "}
                <div
                  className="!text-card-grey"
                  onClick={() => setShowEditTaxJarModal(true)}
                >
                  {createShortenedText(currentTaxJarCode, windowWidth >= 2500)}
                </div>
                <CopyText showIcon onlyIcon textToCopy={currentTaxJarCode} />
              </div>
            ) : (
              <div
                className="!text-card-grey"
                onClick={() => setShowEditTaxJarModal(true)}
              >
                Not Set
              </div>
            )}
          </div>
        </div>
        <Modal
          visible={showEditTaxJarModal}
          onCancel={() => setShowEditTaxJarModal(false)}
          footer={[
            <Button key="cancel" onClick={() => setShowEditTaxJarModal(false)}>
              Cancel
            </Button>,
            <Button
              key="submit"
              type="primary"
              disabled={!updatedTaxJarCode}
              onClick={() => updateTaxJarMutation.mutate()}
            >
              Update
            </Button>,
          ]}
        >
          <Typography.Title level={4} className="mb-4">
            Edit TaxJar Code
          </Typography.Title>
          <Input
            placeholder="Enter new TaxJar code"
            value={updatedTaxJarCode}
            onChange={(event) => setUpdatedTaxJarCode(event.target.value)}
          />
          <div className="mt-4">
            <Button
              type="link"
              href="https://developers.taxjar.com/api/reference/#get-list-tax-categories"
              target="_blank"
              rel="noopener noreferrer"
            >
              View Tax Categories
            </Button>
          </div>
        </Modal>

        <div className="flex items-center justify-between text-card-text gap-2 mb-2">
          <div className="font-normal whitespace-nowrap leading-4">
            Linked External IDs
          </div>
          <div>
            {" "}
            <LinkExternalIds
              createExternalLink={createPlanExternalLink}
              deleteExternalLink={deletePlanExternalLink}
              externalIds={plan.external_links.map((l) => l.external_plan_id)}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Plan Tags
          </div>
          <div>
            {" "}
            <DropdownComponent>
              <DropdownComponent.Trigger>
                <PlansTags tags={plan.tags} />
              </DropdownComponent.Trigger>
              <DropdownComponent.Container>
                {plan_tags &&
                  createPlanTagsList(plan.tags, plan_tags).map((tag, index) => (
                    <DropdownComponent.MenuItem
                      onSelect={() => {
                        if (tag.from !== "plans") {
                          const planTags = [...plan.tags];
                          const orgTags = [...plan_tags];

                          const planTagsFromOrg = orgTags.filter(
                            (el) => el.tag_name === tag.tag_name
                          );
                          const tags = [...planTags, ...planTagsFromOrg];

                          createTagMutation({
                            plan_id: plan.plan_id,
                            tags,
                          });
                        } else {
                          const planTags = [...plan.tags];

                          const tags = planTags.filter(
                            (el) => el.tag_name !== tag.tag_name
                          );
                          createTagMutation({
                            plan_id: plan.plan_id,
                            tags,
                          });
                        }
                      }}
                    >
                      <span key={index} className="flex gap-2 justify-between">
                        <span className="flex gap-2 items-center">
                          <Badge.Dot fill={tag.tag_hex} />
                          <span className="text-black">{tag.tag_name}</span>
                        </span>
                        {tag.from === "plans" && (
                          <CheckCircleOutlined className="!text-gold" />
                        )}
                      </span>
                    </DropdownComponent.MenuItem>
                  ))}
                <DropdownComponent.MenuItem
                  onSelect={() => {
                    const tags = [...plan.tags];
                    const newTag = createTags(inputRef.current!.value);
                    tags.push(newTag);
                    createTagMutation({ plan_id: plan.plan_id, tags });
                  }}
                >
                  <input
                    type="text"
                    className="text-black outline-none"
                    placeholder="Custom tag..."
                    ref={inputRef}
                  />
                </DropdownComponent.MenuItem>
              </DropdownComponent.Container>
            </DropdownComponent>
          </div>
        </div>
      </div>
    </div>
  );
}

interface PlanInfoProps {
  version: PlanVersionType;
  plan: PlanDetailType;
}
export function PlanInfo({ version, plan }: PlanInfoProps) {
  const constructBillType = (str: string) => {
    if (str.includes("_")) {
      return str
        .split("_")
        .map((el) => capitalize(el))
        .join(" ");
    }
    return str;
  };
  const queryClient = useQueryClient();
  const schedule = (duration: "monthly" | "yearly" | "quarterly") => {
    switch (duration) {
      case "monthly":
        return "Start of Month";
      case "quarterly":
        return "Start of Quarter";

      default:
        return "Start of Year";
    }
  };

  const archivemutation = useMutation(
    (version_id: string) =>
      Plan.archivePlanVersion(version_id, { status: "archived" }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
      },
    }
  );
  const menu = (
    <Menu>
      <Menu.Item
        key="1"
        onClick={() => archivemutation.mutate(version!.version_id)}
        disabled={
          version?.status === "active" || version?.status === "grandfathered"
        }
      >
        <div className="planMenuArchiveIcon">
          <div>
            <DeleteOutlined />
          </div>
          <div className="archiveLabel">Archive</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-alliance rounded-sm bg-card ">
      <div className='flex justify-between'>
        <Typography.Title className="pt-4 whitespace-pre-wrap grid gap-4 !text-[18px] items-center grid-cols-1 md:grid-cols-2">
          <div>Plan Information</div>
        </Typography.Title>
        <div className="flex flex-row  items-center font-bold tabsContainer">
            <StateTabs
              activeTab={capitalize(version.status)}
              version_id={version.version_id}
              version={version.version}
              activeVersion={version.version}
              tabs={["Active", "Grandfathered", "Retiring", "Inactive"]}
              plan={plan}
            />
            <span className="ml-auto" onClick={(e) => e.stopPropagation()}>
              <Dropdown overlay={menu} trigger={["click"]}>
                <Button
                  type="text"
                  size="small"
                  onClick={(e) => e.preventDefault()}
                >
                  <EllipsisOutlined />
                </Button>
              </Dropdown>
            </span>
          </div>
      </div>
      <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
      <div className="grid  items-center grid-cols-1 md:grid-cols-2">
        <div className="w-[240px]">
          <div className="flex items-center text-card-text justify-between mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Recurring Price
            </div>
            <div className="flex gap-1">
              {" "}
              <div className="text-gold">{`${plan.display_version.currency.symbol}${plan.display_version.flat_rate}`}</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Plan Duration
            </div>
            <div className="!text-card-grey">
              {capitalize(plan.plan_duration)}
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Created At
            </div>
            <div className="!text-card-grey">
              {" "}
              {dayjs(version?.created_on).format("YYYY/MM/DD")}
            </div>
          </div>
        </div>

        <div className="w-[254px] ml-auto">
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Plan on next cycle
            </div>
            <div className="flex gap-1 ">
              {" "}
              <div className="!text-card-grey">
                {version?.transition_to
                  ? capitalize(version.transition_to)
                  : "Self"}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Recurring Bill Type
            </div>
            <div>
              <Badge>
                <Badge.Content>
                  <div className="p-1">
                    {constructBillType(
                      plan.display_version.flat_fee_billing_type
                    )}
                  </div>
                </Badge.Content>
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Schedule
            </div>
            <div>
              {" "}
              <span>{schedule(plan.plan_duration)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
const PlanComponents: FC<PlanComponentsProps> = ({
  components,
  plan,
  refetch,
  updateBillingFrequencyMutation,
  alerts,
  plan_version_id,
}) => {
  const selectRef = useRef<HTMLSelectElement | null>(null!);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState(0);
  const [isCreateAlert, setIsCreateAlert] = useState(true);
  const [currentComponent, setCurrentComponent] = useState<Component>();
  const [currentAlertId, setCurrentAlertId] = useState<string>();
  const [isInvalid, setIsInvalid] = useState(false);
  const queryClient = useQueryClient();
  const createAlertMutation = useMutation(
    (post: CreateAlertType) => Plan.createAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);

        setAlertThreshold(0);
        refetch();
        toast.success("Successfully created alert.");
        // window.location.reload(false);
      },
    }
  );

  const deleteAlertMutation = useMutation(
    (post: { usage_alert_id: string }) => Plan.deleteAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);

        refetch();
        // toast.success("Deleted alert");
      },
    }
  );
  useEffect(() => {}, [plan]);
  const deleteAlert = (usage_alert_id: string) => {
    deleteAlertMutation.mutate({
      usage_alert_id,
    });
  };

  const showModal = () => {
    setIsModalVisible(true);
  };

  const handleDeleteAlert = () => {
    deleteAlertMutation.mutate({
      usage_alert_id: currentAlertId as string,
    });
    queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
  };

  const submitAlertModal = (component: Component, usage_alert_id?: string) => {
    if (typeof alertThreshold !== "number") {
      toast.error("Must input a number");
      return;
    }
    if (isCreateAlert) {
      createAlertMutation.mutate({
        plan_version_id,
        metric_id: component.billable_metric.metric_id,
        threshold: alertThreshold,
      });
    } else {
      if (usage_alert_id !== undefined) {
        deleteAlertMutation.mutate({
          usage_alert_id,
        });
      }
      createAlertMutation.mutate({
        plan_version_id,
        metric_id: component.billable_metric.metric_id,
        threshold: alertThreshold,
      });
    }
    queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
  };

  return (
    <div className="">
      {components && components.length > 0 ? (
        <div className="mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card ">
          <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
            Added Components
          </Typography.Title>
          <div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          </div>
          <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
            {components.map((component) => (
              <div
                className="pt-2 bg-primary-50 mt-2 relative mb-2 px-4 min-h-[152px] min-w-[270px]"
                key={component.id}
              >
                <div className="text-base text-card-text align-middle">
                  <div> {component.billable_metric.metric_name}</div>
                </div>
                <div>
                  <div className=" w-full h-[1.5px] mt-4 bg-card-divider mb-4" />
                  <Table
                    dataSource={component.tiers}
                    pagination={false}
                    showHeader={false}
                    bordered={false}
                    className="noborderTable h-48 overflow-auto"
                    size="middle"
                    columns={[
                      {
                        title: "Range",
                        dataIndex: "range_start",
                        key: "range_start",
                        align: "left",
                        width: "50%",
                        className: "bg-primary-50 pointer-events-none",
                        render: (value, record) => (
                          <span>
                            From {value} to{" "}
                            {record.range_end == null ? "∞" : record.range_end}
                          </span>
                        ),
                      },
                      {
                        title: "Cost",
                        align: "left",
                        dataIndex: "cost_per_batch",
                        key: "cost_per_batch",
                        className:
                          "bg-primary-50 pointer-events-none !text-card-grey arr",
                        render: (_, record) => (
                          <div>
                            {renderCost(record, component.pricing_unit)}
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>
                <div className="w-[96%] h-[1.5px] bg-card-divider" />
                <div className="self-end">
                  <div
                    className="flex py-6"
                    aria-hidden
                    onClick={() => {
                      if (component.billable_metric.metric_type !== "counter") {
                        toast.error("Only counter metrics can create alerts");
                      } else {
                        if (
                          findAlertForComponent(component, alerts) !== undefined
                        ) {
                          const alert = findAlertForComponent(
                            component,
                            alerts
                          );
                          setIsCreateAlert(false);
                          setAlertThreshold(alert!.threshold);
                          setCurrentAlertId(alert?.usage_alert_id);
                        } else {
                          setIsCreateAlert(true);
                        }
                        setCurrentComponent(component);
                        showModal();
                      }
                    }}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      width="24"
                      height="24"
                      className="mr-2"
                    >
                      <path fill="none" d="M0 0h24v24H0z" />
                      <path d="M20 17h2v2H2v-2h2v-7a8 8 0 1 1 16 0v7zm-2 0v-7a6 6 0 1 0-12 0v7h12zm-9 4h6v2H9v-2z" />
                    </svg>
                    {findAlertForComponent(component, alerts) !== undefined ? (
                      <span className="align-middle">
                        Reaches:{" "}
                        {findAlertForComponent(component, alerts)?.threshold}
                      </span>
                    ) : (
                      <span className=" text-small mb-0 align-middle self-center">
                        Set Alert
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <Modal
              title="Set Alert"
              visible={isModalVisible}
              onCancel={() => setIsModalVisible(false)}
              footer={
                isCreateAlert
                  ? [
                      <Button
                        key="back"
                        onClick={() => setIsModalVisible(false)}
                      >
                        Cancel
                      </Button>,
                      <Button
                        key="submit"
                        type="primary"
                        disabled={isInvalid}
                        onClick={() => submitAlertModal(currentComponent)}
                      >
                        Create
                      </Button>,
                    ]
                  : [
                      <Button
                        key="delete"
                        className=" bg-red-600"
                        onClick={() => deleteAlert(currentAlertId)}
                      >
                        Delete
                      </Button>,
                      <Button
                        key="submit"
                        type="primary"
                        disabled={isInvalid}
                        onClick={() =>
                          submitAlertModal(currentComponent, currentAlertId)
                        }
                      >
                        Update
                      </Button>,
                    ]
              }
            >
              <div className="flex flex-col justify-center items-center gap-4">
                {currentComponent?.billable_metric.metric_name} reaches:{"  "}
                <InputNumber
                  type="number"
                  pattern="[0-9]+"
                  onChange={(value) => {
                    if (value && typeof value === "number") {
                      setAlertThreshold(value);
                      setIsInvalid(false);
                    }
                    if (value === null) {
                      setIsInvalid(true);
                    }
                  }}
                  value={alertThreshold}
                />
                {isInvalid && (
                  <div className="text-red-800">Please enter a number</div>
                )}
              </div>
            </Modal>
          </div>
          <div>
            <Select>
              <Select.Label className="">Billing Frequency</Select.Label>
              <Select.Select
                disabled
                className="!w-1/4"
                onChange={(e) => {
                  updateBillingFrequencyMutation(
                    e.target.value as "monthly" | "quarterly" | "yearly"
                  );
                }}
                ref={selectRef}
              >
                <Select.Option selected>{plan.plan_duration}</Select.Option>
                {["quarterly", "yearly"].map((el) => (
                  <Select.Option>{el}</Select.Option>
                ))}
              </Select.Select>
            </Select>
          </div>
        </div>
      ) : (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title level={2}>Added Components</Typography.Title>
          <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          <div className="text-card-grey text-base">No components added</div>
        </div>
      )}
    </div>
  );
};
export default PlanComponents;