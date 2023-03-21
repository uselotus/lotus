// @ts-ignore
import React, { FC, useRef } from "react";
import { Menu, Dropdown, Button, Typography, Tag } from "antd";
import {
  DeleteOutlined,
  CheckCircleOutlined,
  MoreOutlined,
} from "@ant-design/icons";
import { PlanType, UpdatePlanType } from "../../../types/plan-type";
import "./PlanCard.css";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Plan } from "../../../api/api";
import CopyText from "../../base/CopytoClipboard";
import DropdownComponent from "../../base/Dropdown/Dropdown";
import createShortenedText from "../../../helpers/createShortenedText";
import capitalize from "../../../helpers/capitalize";
import PlansTags from "../PlanTags";
import Badge from "../../base/Badges/Badges";
import useMediaQuery from "../../../hooks/useWindowQuery";
import createTags from "../helpers/createTags";
import useGlobalStore from "../../../stores/useGlobalstore";
import createPlanTagsList from "../helpers/createPlanTagsList";

interface PlanCardProps {
  plan: PlanType;
  pane: "All" | "Monthly" | "Yearly" | "Quarterly";
  createTagMutation: (variables: {
    plan_id: string;
    tags: PlanType["tags"];
    pane: "All" | "Monthly" | "Yearly" | "Quarterly";
  }) => void;
}

const PlanCard: FC<PlanCardProps> = ({ plan, createTagMutation, pane }) => {
  const { plan_tags } = useGlobalStore((state) => state.org);

  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const windowWidth = useMediaQuery();
  const inputRef = useRef<HTMLInputElement | null>(null!);
  const mutation = useMutation((plan_id: string) => Plan.deletePlan(plan_id), {
    onSuccess: () => {
      queryClient.invalidateQueries(["plan_list"]);

      toast.success("Plan archived");
    },
    onError: () => {
      toast.error("Cannot archive plan");
    },
  });

  const planMenu = (
    <Menu>
      <Menu.Item
        key="1"
        onClick={() => mutation.mutate(plan.plan_id)}
        disabled={plan.active_subscriptions > 0}
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

  const gotoPlanDetail = () => {
    navigate(`/plans/${plan.plan_id}`);
  };

  // const computeNumVersions = (plan: PlanType) => {
  //   if (plan.plan_versions.length === 0) return 0;

  const customerNameOrID = (target_customer: any | undefined) => {
    if (target_customer.customer_name) {
      return target_customer.customer_name;
    }
    return target_customer.customer_id;
  };

  return (
    <div
      className="min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-card  shadow-lg hover:shadow-neutral-400"
      onClick={(e) => {
        if ((e.target as HTMLInputElement).nodeName === "DIV") gotoPlanDetail();
      }}
    >
      <div className="pt-4 flex font-alliance text-2xl">
        <span>{plan.plan_name}</span>
        <span className="ml-auto" onClick={(e) => e.stopPropagation()}>
          <Dropdown overlay={planMenu} trigger={["click"]}>
            <Button
              type="text"
              size="small"
              onClick={(e) => e.preventDefault()}
            >
              <MoreOutlined />
            </Button>
          </Dropdown>
        </span>
      </div>

      <div className="text-sm">
        <div>
          <div className="mb-2">
            <div className="pr-1 font-normal font-alliance not-italic whitespace-nowrap  text-darkgold">
              Total Active Subscriptions: {plan.active_subscriptions}
            </div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider" />
          </div>

          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Plan ID
            </div>
            <div className="flex gap-1 text-card-grey font-menlo">
              {" "}
              <div>
                {createShortenedText(plan.plan_id, windowWidth >= 2500)}
              </div>
              <CopyText showIcon onlyIcon textToCopy={plan.plan_id} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            # of versions:
          </div>
          <div className="text-card-grey font-main">{plan.num_versions}</div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Active Version
          </div>
          <div className="text-card-grey font-main">
            {" "}
            v{plan.active_version}
          </div>
        </div>

        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className="font-normal text-card-text whitespace-nowrap leading-4xs">
            Plan duration:
          </div>
          <div className="text-card-grey font-main">
            {" "}
            {plan.plan_duration && capitalize(plan.plan_duration)}
          </div>
        </div>
        <div className="flex mt-2">
          <DropdownComponent>
            <DropdownComponent.Trigger>
              <PlansTags showAddTagButton tags={plan.tags} />
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
                          pane,
                        });
                      } else {
                        const planTags = [...plan.tags];

                        const tags = planTags.filter(
                          (el) => el.tag_name !== tag.tag_name
                        );
                        createTagMutation({
                          plan_id: plan.plan_id,
                          tags,
                          pane,
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

                  createTagMutation({ plan_id: plan.plan_id, tags, pane });
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
  );
};
export default PlanCard;
