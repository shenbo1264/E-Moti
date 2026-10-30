package com.emoti.companion.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.emoti.companion.data.MemoryCard
import com.emoti.companion.data.MemorySource
import com.emoti.companion.state.ChatLine
import com.emoti.companion.state.CompanionViewModel
import com.emoti.companion.state.LineStatus
import com.emoti.companion.state.Phase
import com.emoti.companion.state.Role
import com.emoti.companion.state.UiState

private const val MAX_TEXT = 240

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompanionApp(vm: CompanionViewModel) {
    val state by vm.state.collectAsState()
    val paired = state.phase !in setOf(Phase.Unpaired, Phase.Pairing, Phase.Unauthorized)
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(paired) {
        if (paired) lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) { vm.foregroundSync() }
    }
    if (!paired) {
        PairScreen(state, vm.defaultDeviceName, vm::pair)
        return
    }
    var tab by rememberSaveable { mutableStateOf(0) }
    Scaffold(
        topBar = { TopAppBar(title = { Text(titleFor(state)) }) },
        bottomBar = {
            NavigationBar {
                listOf("聊天", "回忆", "连接").forEachIndexed { index, label ->
                    NavigationBarItem(selected = tab == index, onClick = { tab = index },
                        icon = { Text(label.take(1)) }, label = { Text(label) })
                }
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            StatusBanner(state, vm::dismissNotice)
            when (tab) {
                0 -> ChatScreen(state, vm::send, vm::retry, vm::cancelReply)
                1 -> MemoryScreen(state, vm)
                else -> ConnectionScreen(state, vm::refresh, vm::unpair)
            }
        }
    }
}

private fun titleFor(state: UiState) = when (state.phase) {
    Phase.Online -> "E-Moti · 在线"
    Phase.Offline -> "E-Moti · 电脑离线"
    else -> "E-Moti · 连接中"
}

@Composable
private fun StatusBanner(state: UiState, onDismiss: () -> Unit) {
    val text = when {
        state.error != null -> state.error
        state.phase == Phase.Offline -> "连不上电脑。显示的内容可能已过期，恢复连接后会先刷新再显示。"
        state.notice != null -> state.notice
        else -> null
    } ?: return
    Card(Modifier.fillMaxWidth().padding(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(text, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            if (state.phase != Phase.Offline) TextButton(onClick = onDismiss) { Text("知道了") }
        }
    }
}

@Composable
fun PairScreen(state: UiState, defaultName: String, onPair: (String, String, String) -> Unit) {
    var url by rememberSaveable { mutableStateOf("http://127.0.0.1:8765") }
    var code by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf(defaultName) }
    Column(Modifier.fillMaxSize().padding(20.dp).imePadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("连接你的电脑", style = MaterialTheme.typography.headlineSmall)
        Text("在电脑端打开“手机连接”，开启后生成邀请码。USB 真机先在电脑运行 adb reverse tcp:8765 tcp:8765；模拟器地址用 http://10.0.2.2:8765。",
            style = MaterialTheme.typography.bodyMedium)
        Text("配对后可以和当前角色聊天、管理回忆。手机不会观察屏幕，也不能执行电脑任务。",
            style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(url, { url = it }, Modifier.fillMaxWidth(), label = { Text("电脑地址") }, singleLine = true)
        OutlinedTextField(code, { code = it.trim() }, Modifier.fillMaxWidth(), label = { Text("邀请码（5 分钟内有效）") })
        OutlinedTextField(name, { name = it.take(80) }, Modifier.fillMaxWidth(), label = { Text("这台手机的名字") }, singleLine = true)
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = { onPair(url, code, name.ifBlank { "Android" }) },
            enabled = state.phase != Phase.Pairing && code.length >= 32,
            modifier = Modifier.fillMaxWidth()) {
            Text(if (state.phase == Phase.Pairing) "正在配对…" else "配对")
        }
    }
}

@Composable
private fun ChatScreen(state: UiState, onSend: (String) -> Unit, onRetry: (String) -> Unit, onCancel: () -> Unit) {
    var draft by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.size - 1)
    }
    Column(Modifier.fillMaxSize().imePadding()) {
        LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp), state = listState,
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (state.messages.isEmpty()) item {
                Text("和${state.characterId.ifEmpty { "她" }}说点什么吧。说“请记住……”会先放进待确认，在回忆页确认后才会记住。",
                    Modifier.padding(vertical = 16.dp), style = MaterialTheme.typography.bodyMedium)
            }
            items(state.messages, key = { it.id }) { line -> ChatBubble(line, onRetry) }
        }
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(draft, { draft = it.take(MAX_TEXT) }, Modifier.weight(1f),
                placeholder = { Text("说点什么") }, maxLines = 4)
            Spacer(Modifier.width(8.dp))
            if (state.replyRequestId != null) {
                OutlinedButton(onClick = onCancel) { Text("取消") }
            } else {
                Button(onClick = { onSend(draft); draft = "" },
                    enabled = draft.isNotBlank() && state.phase == Phase.Online) { Text("发送") }
            }
        }
    }
}

@Composable
private fun ChatBubble(line: ChatLine, onRetry: (String) -> Unit) {
    val mine = line.role == Role.User
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (mine) Alignment.End else Alignment.Start) {
        Card(colors = CardDefaults.cardColors(containerColor =
            if (mine) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant)) {
            Text(line.text, Modifier.padding(10.dp))
        }
        val status = when (line.status) {
            LineStatus.Delivering -> "发送中"
            LineStatus.Running -> "她在想…"
            LineStatus.DeliveryUnknown -> line.note ?: "投递状态未知"
            LineStatus.Cancelled, LineStatus.Stale, LineStatus.Rejected -> line.note
            LineStatus.Completed -> line.note
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            status?.let { Text(it, style = MaterialTheme.typography.labelSmall) }
            if (line.status == LineStatus.DeliveryUnknown) TextButton(onClick = { onRetry(line.id) }) { Text("重试") }
        }
    }
}

@Composable
private fun MemoryScreen(state: UiState, vm: CompanionViewModel) {
    var adding by remember { mutableStateOf(false) }
    var correcting by remember { mutableStateOf<MemoryCard?>(null) }
    var forgetting by remember { mutableStateOf<MemoryCard?>(null) }
    var source by remember { mutableStateOf<MemorySource?>(null) }
    val album = state.album
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(album?.title ?: "回忆册", style = MaterialTheme.typography.titleMedium)
                    album?.subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
                Button(onClick = { adding = true }, enabled = state.phase == Phase.Online) { Text("记住一件事") }
            }
        }
        if (album == null) item { Text("正在从电脑读取回忆…", Modifier.padding(16.dp)) }
        val pending = album?.pendingCandidates.orEmpty()
        if (pending.isNotEmpty()) item { Text("待确认", style = MaterialTheme.typography.titleSmall) }
        items(pending, key = { "p-" + it.pendingId }) { candidate ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(candidate.summary)
                    Text("确认后才会被记住和用于聊天。", style = MaterialTheme.typography.labelSmall)
                    Button(onClick = { vm.confirm(candidate.pendingId) }, enabled = state.phase == Phase.Online) { Text("确认记住") }
                }
            }
        }
        album?.sections.orEmpty().forEach { section ->
            item(key = "s-" + section.category) { Text(section.category, style = MaterialTheme.typography.titleSmall) }
            items(section.cards, key = { "c-" + it.cardId }) { card ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(card.title, style = MaterialTheme.typography.labelMedium)
                        Text(card.body, maxLines = 4, overflow = TextOverflow.Ellipsis)
                        Text("${card.whenLabel} · ${card.moodLabel}", style = MaterialTheme.typography.labelSmall)
                        Row {
                            TextButton(onClick = { vm.loadSource(card.cardId) { source = it } }) { Text("来源") }
                            if ("纠正" in card.actions) TextButton(onClick = { correcting = card }) { Text("纠正") }
                            if ("忘记" in card.actions) TextButton(onClick = { forgetting = card }) { Text("忘记") }
                        }
                    }
                }
            }
        }
        if (album != null && album.sections.isEmpty() && pending.isEmpty()) item {
            Text("还没有回忆。你可以直接让她记住一件事。", Modifier.padding(16.dp))
        }
    }
    if (adding) TextDialog("记住一件事", "", onDismiss = { adding = false }) { text -> vm.remember(text); adding = false }
    correcting?.let { card ->
        TextDialog("纠正这条回忆", card.body, onDismiss = { correcting = null }) { text ->
            vm.correct(card.cardId, card.title, text); correcting = null
        }
    }
    forgetting?.let { card ->
        AlertDialog(onDismissRequest = { forgetting = null },
            title = { Text("忘记这件事？") },
            text = { Text("“${card.body}”以及由它派生的摘要都会失效，电脑和手机都不会再用它。") },
            confirmButton = { TextButton(onClick = { vm.forget(card.cardId); forgetting = null }) { Text("忘记") } },
            dismissButton = { TextButton(onClick = { forgetting = null }) { Text("保留") } })
    }
    source?.let { s ->
        AlertDialog(onDismissRequest = { source = null }, title = { Text("回忆来源") },
            text = {
                Text(buildString {
                    appendLine(s.summary)
                    appendLine("来源：${sourceLabel(s.source)}")
                    if (s.version > 0) appendLine("版本：${s.version}")
                    appendLine(if (s.userConfirmed) "你已确认" else "未经你确认")
                    if (!s.active) appendLine("当前已失效")
                })
            },
            confirmButton = { TextButton(onClick = { source = null }) { Text("关闭") } })
    }
}

private fun sourceLabel(source: String) = when (source) {
    "explicit_user_request" -> "你亲口要求记住"
    "user_correction" -> "你的纠正"
    "" -> "未记录"
    else -> source
}

@Composable
private fun TextDialog(title: String, initial: String, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var text by remember { mutableStateOf(initial) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) },
        text = { OutlinedTextField(text, { text = it.take(MAX_TEXT) }, supportingText = { Text("${text.length}/$MAX_TEXT") }) },
        confirmButton = { TextButton(onClick = { onConfirm(text) }, enabled = text.isNotBlank()) { Text("确定") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } })
}

@Composable
private fun ConnectionScreen(state: UiState, onRefresh: () -> Unit, onUnpair: () -> Unit) {
    var confirmUnpair by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("电脑：${state.hostUrl}")
        Text("当前角色：${state.characterId}")
        Text("状态：" + when (state.phase) {
            Phase.Online -> "在线"
            Phase.Offline -> "离线（电脑可能关闭了手机连接或休眠）"
            else -> "连接中"
        })
        Text("可用能力", style = MaterialTheme.typography.titleSmall)
        Text("聊天：${onOff(state.capabilities.chat)}　回忆管理：${onOff(state.capabilities.memory)}")
        Text("观察手机：${onOff(state.capabilities.observations)}　电脑任务：${onOff(state.capabilities.relay)}")
        Text("取消回复只停止电脑端发布，已经发给模型服务的计算不会被撤回。", style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = onRefresh) { Text("立即刷新") }
        OutlinedButton(onClick = { confirmUnpair = true }) { Text("在本机移除配对") }
        Text("移除只删除手机上的凭据；要让凭据立即失效，请同时在电脑端“已配对设备”里撤销。",
            style = MaterialTheme.typography.bodySmall)
    }
    if (confirmUnpair) AlertDialog(onDismissRequest = { confirmUnpair = false }, title = { Text("移除配对？") },
        text = { Text("手机上的聊天缓存和凭据会被清除。") },
        confirmButton = { TextButton(onClick = { confirmUnpair = false; onUnpair() }) { Text("移除") } },
        dismissButton = { TextButton(onClick = { confirmUnpair = false }) { Text("取消") } })
}

private fun onOff(value: Boolean) = if (value) "已开启" else "未开放"
